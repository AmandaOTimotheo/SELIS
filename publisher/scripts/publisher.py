
"""Main orchestration entrypoint for the publisher pipeline.

This module validates configuration, orchestrates data preparation, executes
simulation workloads, and triggers optional analytics/reporting stages.
"""

import argparse
import asyncio
import json
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import debugpy
import pandas as pd
import paho.mqtt.client as mqtt

from capex_opex_analysis import (
    edge_fog_capex_opex_report,
    generate_general_dashboard_with_currency,
    panel_capex_opex_report,
)
from clustering.clustering import clustering
from clustering.create_maps import create_density_map
from msg_colision.msg_collision_analysis import simulate_collision_analysis
from parameters_model_v2 import ParametersV2
from simulation.consumption_analysis import analysis_estimated_vs_simulated
from simulation.device_simulation import (
    run_device_realtime_group_process,
    run_device_simulation_process,
)
from simulation.devices.edges_fogs.publisher_edge_fog import publish_edge_fog_generator
from simulation.devices.panels.publisher_panel import publish_panel_generator


def ensure_output_directories(p: ParametersV2) -> None:
    """Create output directories declared in the parameters when missing."""
    paths: list[str | None] = [
        p.path_json,
        p.clustering.final_path,
        p.clustering.interactive_map_path,
        p.collision.save_data_path,
        p.financial.general.save_report_path,
    ]

    for device_name in type(p.simulation.devices).model_fields.keys():
        device = getattr(p.simulation.devices, device_name)
        paths.append(device.modes.offline_simulation.save_data_path)

    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()

        dir_path = path.parent if path.suffix else path
        dir_path.mkdir(parents=True, exist_ok=True)


def handle_message_collision(p: ParametersV2) -> None:
    """Run message collision analysis when enabled."""
    if p.collision.enable:
        simulate_collision_analysis(p)


def handle_density_map(p: ParametersV2) -> None:
    """Generate a density map from raw spatial data when enabled."""
    if p.clustering.generate_density_map:
        create_density_map(p)


def handle_clustering(p: ParametersV2) -> list[list[Any]]:
    """Return device datasets, clustering first when required.

    If clustering is explicitly enabled, or required cache files do not exist,
    this function executes clustering and returns its outputs. Otherwise, it
    loads cached CSV inputs for each relevant device.
    """
    must_cluster = p.clustering.clustering
    device_names = list(type(p.clustering.devices).model_fields.keys())
    devices_need_data = []
    for name in device_names:
        device_fin = getattr(p.financial.devices, name)
        device_sim = getattr(p.simulation.devices, name)
        need_device_data = (
            device_fin.enable_capex
            or device_fin.enable_opex
            or device_sim.modes.offline_simulation.enable
            or device_sim.modes.real_time_simulation.enable
        )
        if need_device_data:
            devices_need_data.append(name)

    have_cached = all(
        os.path.exists(getattr(p.simulation.devices, name).database.path)
        for name in devices_need_data
    )

    if must_cluster or not have_cached:
        return clustering(p)

    df_devices = []
    for device_name in device_names:
        device_fin = getattr(p.financial.devices, device_name)
        device_sim = getattr(p.simulation.devices, device_name)

        need_device_data = (
            device_fin.enable_capex
            or device_fin.enable_opex
            or device_sim.modes.offline_simulation.enable
            or device_sim.modes.real_time_simulation.enable
        )

        if need_device_data:
            device_path = device_sim.database.path
            df_device = pd.read_csv(device_path, sep=";", decimal=",").reset_index(drop=True)
            required_fields = device_sim.database.fields.model_dump().values()
            needed_fields = set(required_fields) - set(df_device.columns)
            if needed_fields:
                raise ValueError(
                    f"{device_name} database is missing required field(s): {needed_fields}"
                )
        else:
            df_device = pd.DataFrame()

        df_devices.append([device_name, df_device])

    return df_devices


def handle_capex_opex_reports(p: ParametersV2, df_devices: list):
    """Generate CAPEX/OPEX reports and the combined dashboard when possible."""
    device_functions = {
        "panel": panel_capex_opex_report,
        "edge_fog": edge_fog_capex_opex_report,
    }

    enable_capex_opex_dashboard = True
    reports = []
    printed_financial_header = False
    for device_name, df_device in df_devices:
        device_fin = getattr(p.financial.devices, device_name)
        enable_capex = device_fin.enable_capex
        enable_opex = device_fin.enable_opex
        enable_capex_opex_dashboard = enable_capex_opex_dashboard and (enable_capex and enable_opex)

        if enable_capex or enable_opex:
            if not printed_financial_header:
                print("\n" + "-" * 100 + "\n" + "-" * 100)
                print("Starting financial report generation...")
                printed_financial_header = True
            print(f"\nGenerating {device_name} financial report...")
            financial_fn = device_functions.get(device_name)
            if not financial_fn:
                raise ValueError(f"No financial function registered for device: {device_name}")
            if df_device is None or df_device.empty:
                print(
                    f"Warning: No data available for {device_name}. "
                    "Skipping its financial report generation."
                )
                continue
            report = financial_fn(df_device, p)
            reports.append((device_name, report))

    if enable_capex_opex_dashboard and reports:
        print("\nGenerating Financial Dashboard...")
        generate_general_dashboard_with_currency(p, df_devices, reports)


def handle_estimated_calculation(p: ParametersV2, df_devices: list):
    """Run estimated-vs-simulated financial analysis when enabled."""
    if p.financial.general.estimated_vs_simulated.enable:
        print("\n" + "-" * 100 + "\n" + "-" * 100)
        print("Generating comparison between Estimated and Simulated Consumption...")
        analysis_estimated_vs_simulated(p, df_devices)


async def handle_simulation(p: ParametersV2, df_devices: list):
    """Execute offline simulations and spawn real-time simulation processes."""
    device_functions = {
        "panel": publish_panel_generator,
        "edge_fog": publish_edge_fog_generator,
    }

    tasks = []
    offline_jobs = []
    realtime_jobs = []

    any_sim_enabled = False
    for device_name, _ in df_devices:
        device_sim = getattr(p.simulation.devices, device_name)
        if (
            device_sim.modes.offline_simulation.enable
            or device_sim.modes.real_time_simulation.enable
        ):
            any_sim_enabled = True
            break

    if not any_sim_enabled:
        return []

    print("\n" + "-" * 100 + "\n" + "-" * 100)
    print("Starting simulation generation...\n")

    for device_name, df_device in df_devices:
        device_sim = getattr(p.simulation.devices, device_name)
        generator_fn = device_functions.get(device_name)
        if not generator_fn:
            raise ValueError(f"No simulation generator registered for device: {device_name}")
        needs_sim_data = (
            device_sim.modes.offline_simulation.enable
            or device_sim.modes.real_time_simulation.enable
        )
        if df_device is None or df_device.empty:
            if needs_sim_data:
                print(
                    f"Warning: No data available for {device_name}. "
                    "Skipping its simulation or real-time generation."
                )
            continue

        if device_sim.modes.offline_simulation.enable:
            offline_jobs.append((device_name, df_device))

        if device_sim.modes.real_time_simulation.enable:
            realtime_jobs.append((device_name, df_device))

    if not offline_jobs and not realtime_jobs:
        return []

    
    max_threads = max(2, (os.cpu_count() or 1) // 2)
    max_realtime_threads = max(1, int(max_threads * 0.6))
    max_realtime_threads = min(max_realtime_threads, max_threads - 1) if offline_jobs else max_realtime_threads
    max_offline_threads = max_threads - max_realtime_threads

    def chunk_jobs(jobs, chunks):
        chunk_size = max(1, (len(jobs) + chunks - 1) // chunks)
        return [jobs[i:i + chunk_size] for i in range(0, len(jobs), chunk_size)]

    realtime_procs = []
    if realtime_jobs:
        params = p.model_dump()
        realtime_groups = chunk_jobs(realtime_jobs, max_realtime_threads)
        for group in realtime_groups:
            proc = multiprocessing.Process(
                target=run_device_realtime_group_process,
                args=(params, group),
            )
            proc.start()
            realtime_procs.append(proc)

    total_jobs = len(offline_jobs)
    if total_jobs:
        params = p.model_dump()
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=min(total_jobs, max_offline_threads)) as executor:
            for device_name, df_device in offline_jobs:
                tasks.append(
                    loop.run_in_executor(
                        executor,
                        run_device_simulation_process,
                        params,
                        df_device,
                        device_name,
                    )
                )

    if tasks:
        await asyncio.gather(*tasks)

    return realtime_procs


def build_mqtt_client(p_device):
    """
    Create and connect an MQTT client using a keepalive that is >= the longest
    publish interval configured in the parameters file.
    """
    intervals = [
        p_device.publication_interval_day,
        p_device.publication_interval_night,
    ]
    longest_interval = max([i for i in intervals if i is not None], default=60)
    keepalive = max(longest_interval, 60)

    mqtt_cfg = p_device.modes.real_time_simulation.mqtt

    client = mqtt.Client()
    client.connect(mqtt_cfg.broker_address, mqtt_cfg.broker_port, keepalive)
    print(
        "[MQTT] Connected to "
        f"{mqtt_cfg.broker_address}:{mqtt_cfg.broker_port} with keepalive={keepalive}s"
    )
    return client


async def main(p: ParametersV2):
    """Run the full pipeline in the intended stage order."""
    ensure_output_directories(p)
    handle_density_map(p)
    handle_message_collision(p)

    df_devices = handle_clustering(p)
    handle_capex_opex_reports(p, df_devices)

    realtime_procs = await handle_simulation(p, df_devices)
    handle_estimated_calculation(p, df_devices)

    if realtime_procs:
        print("\nReal-time processes are running. Press Ctrl+C to stop.")
        try:
            while any(proc.is_alive() for proc in realtime_procs):
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping real-time processes...")
            for proc in realtime_procs:
                if proc.is_alive():
                    proc.terminate()
            for proc in realtime_procs:
                proc.join()


def resolve_parameters_path(cli_path: str | None) -> Path:
    """Resolve parameters JSON path from CLI argument, env var, or defaults."""
    if cli_path:
        params_path = Path(cli_path).expanduser().resolve()
        if not params_path.exists():
            raise FileNotFoundError(f"Parameters file not found: {params_path}")
        return params_path

    env_path = os.getenv("PARAMS_PATH")
    if env_path:
        params_path = Path(env_path).expanduser().resolve()
        if not params_path.exists():
            raise FileNotFoundError(f"PARAMS_PATH points to a missing file: {params_path}")
        return params_path

    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / "source" / "default.json",
        Path("/app/source/default.json"),
        Path("/app/publisher/source/default.json"),
        Path.cwd() / "publisher" / "source" / "default.json"
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    candidate_text = "\n - ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        "Could not locate default parameters file (default.json). Checked:\n - "
        + candidate_text
    )


def save_used_parameters(params: dict, p: ParametersV2, source_params_path: Path | None = None) -> Path:
    """Persist runtime parameters, reusing an existing used_parameters file when possible."""
    output_dir = Path(p.path_json).expanduser()
    if not output_dir.is_absolute():
        output_dir = (Path.cwd() / output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    if source_params_path is not None:
        source_resolved = source_params_path.expanduser().resolve()
        if (
            source_resolved.exists()
            and source_resolved.parent == output_dir
            and source_resolved.name.startswith("used_parameters_")
            and source_resolved.suffix.lower() == ".json"
        ):
            return source_resolved

    output_path = output_dir / f"used_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(params, file, indent=4, ensure_ascii=False)

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Generator_Math publisher pipeline.")
    parser.add_argument(
        "--params",
        type=str,
        default=None,
        help="Path to the JSON parameters file. If omitted, default discovery is used.",
    )
    args = parser.parse_args()

    params_path = resolve_parameters_path(args.params)
    with params_path.open("r", encoding="utf-8") as file:
        params = json.load(file)

    p = ParametersV2(**params)
    save_used_parameters(params, p, params_path)

    if p.debug:
        debugpy.listen(("0.0.0.0", 5678))
        print("Waiting for debugger connection...")
        debugpy.wait_for_client()
        print("\nDebugger is now connected.")

    asyncio.run(main(p))
