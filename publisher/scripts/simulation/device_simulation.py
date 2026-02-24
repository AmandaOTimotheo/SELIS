"""Simulation runners for offline and real-time device execution.

This module centralizes process-safe wrappers used by the orchestrator
(`publisher.py`) and keeps execution loops generic for panel and edge/fog
generators.
"""

import asyncio
import time
from datetime import datetime as dt
from typing import Any, Awaitable, Callable

import pandas as pd
import pytz

from simulation.consumption_analysis import save_consumption_report, update_consumption
from simulation.report_functions import (
    storage_and_transmission_size,
    transmission_and_storage_report,
)
from simulation.time_manager import get_interval, load_time


def _format_now(timezone_str: str) -> tuple[str, str]:
    """Return current local time/date strings in the configured timezone."""
    tz = pytz.timezone(timezone_str)
    now = dt.now(tz)
    return now.strftime("%H:%M:%S"), now.strftime("%m/%d/%Y")


def _format_duration(seconds: float) -> str:
    """Convert duration in seconds to a readable text snippet."""
    minutes, sec = divmod(int(seconds), 60)
    if minutes == 0:
        return f"{sec} second{'s' if sec != 1 else ''}"
    return (
        f"{minutes} minute{'s' if minutes != 1 else ''} "
        f"and {sec} second{'s' if sec != 1 else ''}"
    )


async def publish_device_simulation(
    p: Any,
    df: pd.DataFrame,
    *,
    device_key: str,
    generator_fn: Callable[[Any, dt, pd.DataFrame, Any], Awaitable[list[dict]]]
) -> None:
    """Run the generic offline simulation loop for a single device type."""

    device_sim = getattr(p.simulation.devices, device_key, None)
    device_fin = getattr(p.financial.devices, device_key, None)
    if device_sim is None:
        available = list(vars(p.simulation.devices).keys())
        raise ValueError(f"device_key must be one of {available}")

    current_dt, stop_dt = load_time(p, device_key)

    start_time = time.perf_counter()
    current_date_complete = dt.now(pytz.timezone(p.simulation.window.time_zone))
    formatted_time = current_date_complete.strftime("%H:%M:%S")
    formatted_date = current_date_complete.strftime("%m/%d/%Y")
    print(f"\nStarted SIMULATION ({device_key}) at {formatted_time} on {formatted_date}.", flush=True)

    count = 0
    report_consumption: list = []
    last_current_date = current_dt.date()
    file_part_counter = 0
    buffer = pd.DataFrame()
    csv_lines_limit = p.simulation.persistence.csv_lines_limit

    while current_dt < stop_dt:
        count += 1
        _, current_dt = get_interval(p, device_key, current_dt, count)

        data = await generator_fn(p, current_dt, df, client=None)
        df_data = pd.DataFrame(data)

        if device_fin.communication_cost_report.enable_transmission_and_storage:
            df_data = storage_and_transmission_size(df_data, device_fin)

        if device_fin.communication_cost_report.enable_consumption_report:
            report_consumption = update_consumption(
                p,
                report_consumption,
                df_data,
                current_dt,
                device_key,
            )

        buffer = pd.concat([buffer, df_data], ignore_index=True)

        if p.simulation.persistence.save_simulation_data:
            if (
                len(buffer) >= csv_lines_limit
                or current_dt >= stop_dt
                or last_current_date != current_dt.date()
            ):
                if last_current_date != current_dt.date():
                    last_current_date = current_dt.date()
                    file_part_counter = 1

                csv_filename = (
                    f"{device_sim.modes.offline_simulation.save_data_path}/"
                    f"{device_key}_data_{current_dt.strftime('%m-%d-%Y')}_part_{file_part_counter}.csv"
                )

                with open(csv_filename, mode="w", newline="") as file:
                    if len(buffer) >= csv_lines_limit and current_dt >= stop_dt:
                        buffer.iloc[:csv_lines_limit].to_csv(
                            csv_filename,
                            mode="w",
                            index=False,
                            header=True,
                        )
                        buffer = buffer.iloc[csv_lines_limit:]
                    else:
                        buffer.to_csv(
                            csv_filename,
                            mode="w",
                            index=False,
                            header=True,
                        )
                        buffer = buffer.iloc[0:0]
                file_part_counter += 1

    end_time = time.perf_counter()
    total_time_simulation = end_time - start_time

    if device_fin.communication_cost_report.enable_transmission_and_storage:
        transmission_and_storage_report(p, device_key, df_data)

    if device_fin.communication_cost_report.enable_consumption_report:
        save_consumption_report(report_consumption, p, device_key)

    formatted_time, formatted_date = _format_now(p.simulation.window.time_zone)
    print(
        f"\nFinished SIMULATION ({device_key}) at {formatted_time} on {formatted_date}."
    )
    print(
        f"Duration ({device_key}): {_format_duration(total_time_simulation)}\n"
    )


async def publish_device_realtime(
    p: Any,
    df: pd.DataFrame,
    client: Any,
    *,
    device_key: str,
    generator_fn: Callable[[Any, dt, pd.DataFrame, Any], Awaitable[Any]],
) -> None:
    """Generic real-time loop for devices (panels, edge/fog, etc.)."""

    device_sim = getattr(p.simulation.devices, device_key, None)
    if device_sim is None:
        available = list(vars(p.simulation.devices).keys())
        raise ValueError(f"device_key must be one of {available}")

    current_date_complete = dt.now(pytz.timezone(p.simulation.window.time_zone))
    formatted_time = current_date_complete.strftime("%H:%M:%S")
    formatted_date = current_date_complete.strftime("%m/%d/%Y")
    print(f"\nStarted Real-Time ({device_key}) at {formatted_time} on {formatted_date}.")

    current_dt, _ = load_time(p, device_key)

    count = 0
    while True:
        count += 1
        interval, current_dt = get_interval(p, device_key, current_dt, count)

        start_exec = time.time()
        await generator_fn(p, current_dt, df, client)

        exec_time = time.time() - start_exec
        wait_time = max(interval - exec_time, 0)
        await asyncio.sleep(wait_time)


def run_device_simulation_process(
    params: dict,
    df: pd.DataFrame,
    device_key: str,
) -> None:
    """Spawn-safe wrapper that runs an offline simulation for one device type."""
    from parameters_model_v2 import ParametersV2
    from simulation.devices.edges_fogs.publisher_edge_fog import publish_edge_fog_generator
    from simulation.devices.panels.publisher_panel import publish_panel_generator

    generator_by_device = {
        "panel": publish_panel_generator,
        "edge_fog": publish_edge_fog_generator,
    }

    generator_fn = generator_by_device.get(device_key)
    if not generator_fn:
        raise ValueError(f"No simulation generator registered for device: {device_key}")

    p = ParametersV2(**params)
    asyncio.run(
        publish_device_simulation(
            p,
            df,
            device_key=device_key,
            generator_fn=generator_fn,
        )
    )


def run_device_realtime_process(
    params: dict,
    df: pd.DataFrame,
    device_key: str,
) -> None:
    """Spawn-safe wrapper that runs a real-time simulation for one device type."""
    import paho.mqtt.client as mqtt
    from parameters_model_v2 import ParametersV2
    from simulation.devices.edges_fogs.publisher_edge_fog import publish_edge_fog_generator
    from simulation.devices.panels.publisher_panel import publish_panel_generator

    generator_by_device = {
        "panel": publish_panel_generator,
        "edge_fog": publish_edge_fog_generator,
    }

    generator_fn = generator_by_device.get(device_key)
    if not generator_fn:
        raise ValueError(f"No simulation generator registered for device: {device_key}")

    p = ParametersV2(**params)
    device_sim = getattr(p.simulation.devices, device_key, None)
    if device_sim is None:
        available = list(vars(p.simulation.devices).keys())
        raise ValueError(f"device_key must be one of {available}")

    intervals = [
        device_sim.publication_interval_day,
        device_sim.publication_interval_night,
    ]
    longest_interval = max([i for i in intervals if i is not None], default=60)
    keepalive = max(longest_interval, 60)

    mqtt_cfg = device_sim.modes.real_time_simulation.mqtt
    client = mqtt.Client()
    client.connect(mqtt_cfg.broker_address, mqtt_cfg.broker_port, keepalive)

    asyncio.run(
        publish_device_realtime(
            p,
            df,
            client,
            device_key=device_key,
            generator_fn=generator_fn,
        )
    )


def run_device_realtime_group_process(
    params: dict,
    jobs: list[tuple[str, pd.DataFrame]],
) -> None:
    """Spawn-safe wrapper that runs multiple real-time jobs in one process."""
    import paho.mqtt.client as mqtt
    from parameters_model_v2 import ParametersV2
    from simulation.devices.edges_fogs.publisher_edge_fog import publish_edge_fog_generator
    from simulation.devices.panels.publisher_panel import publish_panel_generator

    generator_by_device = {
        "panel": publish_panel_generator,
        "edge_fog": publish_edge_fog_generator,
    }

    async def run_group():
        p = ParametersV2(**params)
        tasks = []
        for device_key, df in jobs:
            generator_fn = generator_by_device.get(device_key)
            if not generator_fn:
                raise ValueError(f"No simulation generator registered for device: {device_key}")

            device_sim = getattr(p.simulation.devices, device_key, None)
            if device_sim is None:
                available = list(vars(p.simulation.devices).keys())
                raise ValueError(f"device_key must be one of {available}")

            intervals = [
                device_sim.publication_interval_day,
                device_sim.publication_interval_night,
            ]
            longest_interval = max([i for i in intervals if i is not None], default=60)
            keepalive = max(longest_interval, 60)

            mqtt_cfg = device_sim.modes.real_time_simulation.mqtt
            client = mqtt.Client()
            client.connect(mqtt_cfg.broker_address, mqtt_cfg.broker_port, keepalive)

            tasks.append(
                publish_device_realtime(
                    p,
                    df,
                    client,
                    device_key=device_key,
                    generator_fn=generator_fn,
                )
            )

        await asyncio.gather(*tasks)

    asyncio.run(run_group())
