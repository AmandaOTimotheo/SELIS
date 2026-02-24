import json
from simulation.report_functions import *
from simulation.consumption_analysis import *
from simulation.generation_common import (
    build_fail_masks,
    generate_measures,
    format_timestamp,
)


# -------------------------------------------------------------------------
# CORE EDGE/FOG GENERATOR (used by both simulation and real-time)
# -------------------------------------------------------------------------

async def publish_edge_fog_generator(p, current_dt, df_edges, client):
    """
    Generates all edge/fog messages for a given timestamp.

    If simulation_mode == True:
        → returns a list of dictionaries (one per edge)

    If real-time_mode == True:
        → publishes MQTT messages (ignores "isFail" rows)

    This function is responsible for:
        - Applying failure masks
        - Generating voltage, current, power factor, consumption
        - Formatting message fields according to payload config
    """

    formatted_time = current_dt.strftime("%H:%M:%S")
    formatted_date = current_dt.strftime("%m/%d/%Y")
    print(f"[Edge/Fog] Generating data for {formatted_time} on {formatted_date}.")
    
    # Check simulation or real-time mode through Pydantic
    sim_modes = p.simulation.devices.edge_fog.modes
    is_simulation = sim_modes.offline_simulation.enable

    # Payload configuration (send flags, headers, decimals)
    cfg = p.financial.devices.edge_fog.payloads
    send_g = cfg.send.general
    send_m = cfg.send.measures
    header_g = cfg.header.general
    header_m = cfg.header.measures
    ndec = cfg.n_decimals.measures

    # Extract generation parameters
    v, c, s = p.simulation.generation.voltage, p.simulation.generation.current, p.simulation.generation.consumption
         
    # Database field mapping
    fields = p.simulation.devices.edge_fog.database.fields

    # Index is normalized upstream; keep defensive reset
    df_edges = df_edges.reset_index(drop=True)

    size = len(df_edges)
    
    rated_voltage = df_edges[fields.rated_voltage].to_numpy()
    rated_power_factor = df_edges[fields.rated_power_factor].to_numpy()
    rated_current = df_edges[fields.rated_current].to_numpy()

    p_device = p.simulation.devices.edge_fog
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
    # BUILD MESSAGES
    # -----------------------------------
    timestamp = format_timestamp(current_dt)
    results = []
    # Iterate edge by edge
    for i, row_df in df_edges.iterrows():
        row = {}

        # GENERAL SECTION
        if send_g.timestamp:
            row[header_g.timestamp] = timestamp
        if send_g.id:
            row[header_g.id] = row_df[fields.edge_id]
        if send_g.fog_id:
            row[header_g.fog_id] = row_df[fields.fog_id]
        if send_g.name:
            row[header_g.name] = row_df[fields.name]
        # Need to Implement
        if send_g.esp_temperature:
            row[header_g.esp_temperature] = 0.0

    
        # MEASURES SECTION
        if send_m.voltage:
            row[header_m.voltage] = round(voltage[i], ndec.voltage)
        if send_m.current:
            row[header_m.current] = round(current[i], ndec.current)
        if send_m.power_factor:
            row[header_m.power_factor] = round(pf[i], ndec.power_factor)
        if send_m.consumption and consumption is not None:
            row[header_m.consumption] = round(consumption[i], ndec.consumption)

        # FAILURE FLAG FOR MESSAGE FILTERING
        row["isFail"] = bool(transmission_fail_mask[i])

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


# def get_formatted_now(params) -> tuple[str, str]:
#     tz = pytz.timezone(params.simulation.window.time_zone)
#     now = datetime.now(tz)
#     return now.strftime("%H:%M:%S"), now.strftime("%m/%d/%Y")


# def format_duration(seconds: float) -> str:
#     minutes, sec = divmod(int(seconds), 60)

#     if minutes == 0:
#         return f"{sec} second{'s' if sec != 1 else ''}"

#     return (
#         f"{minutes} minute{'s' if minutes != 1 else ''} "
#         f"and {sec} second{'s' if sec != 1 else ''}"
#     )
