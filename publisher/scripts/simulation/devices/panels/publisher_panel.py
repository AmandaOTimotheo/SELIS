import asyncio
import json
import numpy as np
from operator import itemgetter
from datetime import datetime as dt
import time
import pandas as pd
from datetime import timedelta
from simulation.time_manager import get_interval
import debugpy
from simulation.report_functions import *
from simulation.consumption_analysis import *
from simulation.generation_common import (
    build_fail_masks,
    generate_measures,
    format_timestamp,
)

# -------------------------------------------------------------------------
# CORE PANEL GENERATOR (used by both simulation and real-time)
# -------------------------------------------------------------------------

async def publish_panel_generator(p, current_dt, df_panels, client):
    """
    Generates all panel messages for a given timestamp.

    If simulation_mode == True:
        → returns a list of dictionaries (one per panel)

    If real-time_mode == True:
        → publishes MQTT messages (ignores "isFail" rows)

    This function is responsible for:
        - Applying failure masks
        - Generating voltage, current, power factor, consumption
        - Formatting message fields according to payload config
        - Grouping by panel ID and computing mean per branch
    """

    # if print_logs is enabled, print the current simulation time
    formatted_time = current_dt.strftime("%H:%M:%S")
    formatted_date = current_dt.strftime("%m/%d/%Y")
    print(f"[Panels] Generating data for {formatted_time} on {formatted_date}.")
    
    # Check simulation or real-time mode through Pydantic
    sim_modes = p.simulation.devices.panel.modes
    is_simulation = sim_modes.offline_simulation.enable

    # Payload configuration (send flags, headers, decimals)
    cfg = p.financial.devices.panel.payloads
    send_g = cfg.send.general
    send_m = cfg.send.measures
    header_g = cfg.header.general
    header_m = cfg.header.measures
    ndec = cfg.n_decimals.measures

    # Extract generation parameters
    # NOTE: The original use of itemgetter with "|" does NOT work for Pydantic models.
    #       You should instead explicitly access fields as shown below:
    v, c, s = p.simulation.generation.voltage, p.simulation.generation.current, p.simulation.generation.consumption

    results = []

    # Group by PANEL number, using mapping from Pydantic config
    fields = p.simulation.devices.panel.database.fields
    
    for panel_id, group in df_panels.groupby(fields.panel_num):

        rated_voltage = group[fields.rated_voltage].to_numpy()
        rated_power_factor = group[fields.rated_power_factor].to_numpy()
        rated_current = group[fields.rated_current].to_numpy()
        
        size = len(group)
        n_branches = int(group[fields.branch_num].max()) 

        p_device = p.simulation.devices.panel
        day_fail_mask, zero_fail_mask, low_fail_mask, transmission_fail_mask = build_fail_masks(
            p_device.failure_rate,
            size,
        )

        voltage, current, pf, consumption = generate_measures(
            p,
            p_device,
            v,
            c,
            s,
            size,
            day_fail_mask, zero_fail_mask, low_fail_mask,
            current_dt,
            send_m.consumption,
            base_voltage=rated_voltage,
            base_current=rated_current,
            base_power_factor=rated_power_factor,
        )

        # -----------------------------------
        # BUILD MESSAGE
        # -----------------------------------
        timestamp = format_timestamp(current_dt)
        row = {}

        # GENERAL SECTION
        if send_g.timestamp:
            row[header_g.timestamp] = timestamp
        if send_g.id:
            row[header_g.id] = group[fields.panel_id].iloc[0]
        if send_g.name:
            row[header_g.name] = group[fields.name].iloc[0]
        # Need to Implement
        if send_g.battery:              
            row[header_g.battery] = 0 
        # Need to Implement
        if send_g.temperature: 
            row[header_g.temperature] = 0.0 
        # Need to Implement
        if send_g.humidity: 
            row[header_g.humidity] = 0 
        # Need to Implement
        if send_g.branches_status: 
            row[header_g.branches_status] = "1" * n_branches

        # MEASURES PER BRANCH
        for b in range(1, n_branches + 1):
            mask = group[fields.branch_num] == b

            if send_m.current:
                row[f"{header_m.current}{b}"] = round(np.sum(current[mask]), ndec.current)
            if send_m.voltage:
                row[f"{header_m.voltage}{b}"] = round(np.mean(voltage[mask]), ndec.voltage)
            if send_m.power_factor:
                row[f"{header_m.power_factor}{b}"] = round(np.mean(pf[mask]), ndec.power_factor)
            if send_m.consumption and consumption is not None:
                row[f"{header_m.consumption}{b}"] = round(np.sum(consumption[mask]), ndec.consumption)

        # FAILURE FLAG FOR MESSAGE FILTERING (majority of branches failing)
        # Mathematical artifice to use the same fail_mask function as other devices
        row["isFail"] = bool(transmission_fail_mask.mean() >= 0.5)

        results.append(row)

    # -----------------------------------
    # SIMULATION MODE → return rows
    # -----------------------------------
    if is_simulation:
        return results

    # -----------------------------------
    # REAL-TIME MODE → publish MQTT
    # -----------------------------------
    topic = sim_modes.real_time_simulation.topics
    for r in results:
        if not r["isFail"]:
            payload = json.dumps(
                {k: v for k, v in r.items() if k != "isFail"},
                ensure_ascii=False
            )
            client.publish(topic, payload)
            # print publish log
            if sim_modes.real_time_simulation.is_print_publish:
                print(f"Published: {payload} to topic: {topic}.")
    return None
