import re
import math
import pandas as pd
from datetime import datetime


def storage_and_transmission_size(df, p_device):
    # Validate send format
    fields_g = p_device.payloads.send.general.model_dump()
    fields_m = p_device.payloads.send.measures.model_dump()
    header_g = p_device.payloads.header.general.model_dump()
    header_m = p_device.payloads.header.measures.model_dump()
    n_decimals = p_device.payloads.n_decimals.measures.model_dump()

    first_row = df.iloc[0]
    active_fields = get_active_fields(first_row, fields_g, fields_m, header_g, header_m)
    
    if p_device.payloads.send.transmission_format == "JSON":
        df["transmission_bytes"] = df.apply(
            lambda row: calculate_json_message_size(
                row=row,
                active_fields = active_fields
            ),
            axis=1
        )
    elif p_device.payloads.send.transmission_format == "CBOR":
        df["transmission_bytes"] = df.apply(
            lambda row: calculate_cbor_message_size(
                row=row,
                active_fields=active_fields,
            ),
            axis=1
        )
    else:
        raise ValueError(
            f"Unsupported send format: {p_device.payloads.send.transmission_format}. "
            "Supported formats: 'JSON','CBOR'."
        )

    # Validate storage format
    if p_device.payloads.save.storage_format == "SQL":
        row_size = calculate_sql_message_size(
            row=first_row,
            active_fields=active_fields,
            n_decimals=n_decimals,
            header_m=header_m
        )
        df["storage_bytes"] = row_size

    elif p_device.payloads.save.storage_format == "CSV":
        df["storage_bytes"] = df.apply(
            lambda row: calculate_csv_message_size(
                row=row,
                active_fields = active_fields
            ),
            axis=1
        ) 
    else:
        raise ValueError(
            f"Unsupported storage format: {p_device.payloads.save.storage_format}. "
            "Supported formats: 'SQL','CSV'."
        )

    return df


def json_kv_size(key: str, value) -> int:
    # tamanho da chave: "key":
    size = len(key) + 2  # aspas da chave
    size += 1            # dois-pontos :

    # tamanho do valor
    if isinstance(value, str):
        size += len(value) + 2
    elif isinstance(value, (int, float)):
        size += len(str(value))
    elif value is None:
        size += 4  # null
    elif isinstance(value, bool):
        size += 4 if value else 5  # true / false
    else:
        size += 0

    return size


def get_active_fields(row, fields_g: dict, fields_m: dict, header_g: dict, header_m: dict) -> list[str]:
    active = []

    # ---------- GENERAL ----------
    for field_name, enabled in fields_g.items():
        if not enabled:
            continue

        header_name = header_g[field_name]
        if header_name in row.index:
            active.append(header_name)

    # ---------- MEASURES ----------
    for field_name, enabled in fields_m.items():
        if not enabled:
            continue

        header_base = header_m[field_name]
        pattern = re.compile(rf"^{header_base}(\d+)$")

        for col in row.index:
            if pattern.match(col):
                active.append(col)

    return active

def calculate_json_message_size(row, active_fields: list) -> int:
                    
    total_size = 0
    n_fields = len(active_fields)

    for i, col in enumerate(active_fields):
        value = row[col]

        total_size += json_kv_size(col, value)

        # comma between fields (excepct the last one)
        if i < n_fields - 1:
            total_size += 1

    # external curly braces { }
    total_size += 2

    return total_size



        
def calculate_sql_message_size(
    row,
    active_fields: list[str],
    n_decimals: dict,
    header_m: dict,
) -> int:

    total_size = 0

    # Logical Inversion
    header_m_inv = {v: k for k, v in header_m.items()}
    
    for col in active_fields:
        value = row[col]

        # ---- size_format ----
        if value is None:
            continue

        if isinstance(value, bool):
            total_size += 1
            continue

        if isinstance(value, int):
            total_size += 4
            continue

        if isinstance(value, str):
            total_size += len(value)
            continue

        if isinstance(value, float):
            # V1 -> V
            base_physical = col.rstrip("0123456789")

            logical = header_m_inv.get(base_physical)

            decimals = n_decimals.get(logical) if logical else None

            # FLOAT vs DOUBLE
            total_size += 4 if decimals is not None and decimals <= 3 else 8
            continue

    return total_size

def cbor_text_size(text: str) -> int:
    length = len(text.encode("utf-8"))
    if length <= 23:
        return 1 + length
    elif length <= 255:
        return 2 + length
    elif length <= 65535:
        return 3 + length
    else:
        return 5 + length


def cbor_value_size(value) -> int:
    if value is None:
        return 1  # null

    if isinstance(value, bool):
        return 1

    if isinstance(value, int):
        if 0 <= value <= 23:
            return 1
        elif value <= 0xFF:
            return 2
        elif value <= 0xFFFF:
            return 3
        elif value <= 0xFFFFFFFF:
            return 5
        else:
            return 9

    if isinstance(value, float):
        return 9  # float64 (major_format 7)

    if isinstance(value, str):
        return cbor_text_size(value)

    return 0


def calculate_cbor_message_size(
    row,
    active_fields: list[str],
) -> int:
    """
    Calcula o tamanho do payload CBOR (bytes) para UMA linha do DataFrame.
    """

    total_size = 0
    n_fields = len(active_fields)

    # ---- map header (major_format 5) ----
    if n_fields <= 23:
        total_size += 1
    elif n_fields <= 255:
        total_size += 2
    elif n_fields <= 65535:
        total_size += 3
    else:
        total_size += 5

    # ---- key-value pairs ----
    for col in active_fields:
        value = row[col]

        # key (text string)
        total_size += cbor_text_size(col)

        # value
        total_size += cbor_value_size(value)

    return total_size


def calculate_csv_message_size(row, active_fields: list) -> int:
    
    # seleciona apenas os valores ativos da linha
    row_active = row[active_fields]

    # converte para string e soma os tamanhos
    cell_sizes = row_active.a_format(str).map(len).sum()

    # delimitadores + newline
    row_size = cell_sizes + (len(active_fields) - 1) + 1

    return row_size


def transmission_and_storage_report(p, device_key, df):
    
    device_fin = getattr(p.financial.devices, device_key, None)
    device_sim = getattr(p.simulation.devices, device_key, None)


    # get total transmission and storage sizes for each panel/fog as lists
    if device_key == "panel":
        transmission_sizes = df["transmission_bytes"].tolist()
        storage_sizes = df["storage_bytes"].tolist()
        
    elif device_key == "edge_fog":
        transmission_sizes = []
        storage_sizes = []
        for _, group_field in df.groupby(device_sim.database.fields.fog_id):
            transmission_sizes.append(group_field["transmission_bytes"].sum())
            storage_sizes.append(group_field["storage_bytes"].sum())
       
    # Get sun time
    daylight = p.simulation.daylight
    sunrise_end = daylight.sunrise_end
    sunset_start = daylight.sunset_start   

    sunrise_end_dt = datetime.combine(datetime.today().date(), sunrise_end)
    sunset_start_dt = datetime.combine(datetime.today().date(), sunset_start)

    # duração do período de sol
    day_time_in_hours = (sunset_start_dt - sunrise_end_dt).total_seconds() / 3600

    cycles_per_hour_day= 3600/device_sim.publication_interval_day
    cycles_per_hour_night= 3600/device_sim.publication_interval_night
    cycles_per_hour = day_time_in_hours*cycles_per_hour_day + (24 - day_time_in_hours)*cycles_per_hour_night
    
    p_transmission = device_fin.communication_cost_report.transmission
    internet_princing = p_transmission.internet_cost_MB_BRL

    internet_use_per_month_MB = []
    internet_plan_mb = []
    internet_plan_price = []
    internet_cost_per_month = []
    mqtt_cost_per_month = []
    conectivity_cost_per_month = []
    transmission_cost_per_month = []
    storage_per_month_GB = []
    storage_cost_per_month = []

    p_storage = device_fin.communication_cost_report.storage

    # prepare internet plans sorted by cap (float)
    plans_sorted = sorted(((float(cap), price) for cap, price in internet_princing.items()), key=lambda x: x[0])

    for t_size, s_size in zip(transmission_sizes, storage_sizes):
        monthly_mb = 24 * 30 * cycles_per_hour * t_size / (1024**2)
        internet_use_per_month_MB.append(monthly_mb)

        # choose internet plan per device
        plan_cap, plan_price = plans_sorted[-1]
        for cap, price in plans_sorted:
            if monthly_mb <= cap:
                plan_cap, plan_price = cap, price
                break
        plan_cap = float(plan_cap)
        plan_price = float(plan_price)
        internet_plan_mb.append(plan_cap)
        internet_plan_price.append(plan_price)
        internet_cost_per_month.append(math.ceil(monthly_mb / plan_cap) * plan_price)

        mqtt_transmissions = t_size * 1024 / p_transmission.max_KBs_per_message
        mqtt_transmissions_per_month = cycles_per_hour * 24 * 30 * mqtt_transmissions
        mqtt_cost_per_month.append(mqtt_transmissions_per_month * p_transmission.cost_per_mqtt_msg)

        conectivity_cost = p_transmission.connectivity_cost_per_minute * 24 * 60 * 30
        conectivity_cost_per_month.append(conectivity_cost)

        transmission_cost_per_month.append(internet_cost_per_month[-1] + mqtt_cost_per_month[-1] + conectivity_cost)

        storage_per_month_GB.append(s_size / 1024**3 * cycles_per_hour * 24 * 30 * p_storage.months_of_storage)
        storage_cost_per_month.append(storage_per_month_GB[-1] * p_storage.storage_cost_per_GB)
    
    # create a report csv file
    # ---------------- Common report ---------------- #

    report_columns = [
        "device",
        "transmission_size_bytes_per_message",
        "storage_size_bytes_per_message",
        "internet_use_per_month_MB",
        "internet_plan_MB",
        "internet_plan_price_BRL",
        "internet_cost_per_month_BRL",
        "mqtt_cost_per_month_BRL",
        "connectivity_cost_per_month_BRL",
        "storage_per_month_GB",
        "storage_cost_per_month_BRL",
        "transmission_cost_per_month_BRL",
        "total_cost_per_month_BRL",
    ]

    report_values = []
    for idx, (
        t_size,
        s_size,
        use_mb,
        plan_mb,
        plan_price,
        internet_cost,
        mqtt_cost,
        conn_cost,
        storage_gb,
        storage_cost,
        trans_cost,
    ) in enumerate(
        zip(
            transmission_sizes,
            storage_sizes,
            internet_use_per_month_MB,
            internet_plan_mb,
            internet_plan_price,
            internet_cost_per_month,
            mqtt_cost_per_month,
            conectivity_cost_per_month,
            storage_per_month_GB,
            storage_cost_per_month,
            transmission_cost_per_month,
        )
    ):
        total_cost = trans_cost + storage_cost
        device_label = f"{device_key}_{idx+1}"
        report_values.append([
            device_label,
            t_size,
            s_size,
            use_mb,
            plan_mb,
            plan_price,
            internet_cost,
            mqtt_cost,
            conn_cost,
            storage_gb,
            storage_cost,
            trans_cost,
            total_cost,
        ])

    df_report = pd.DataFrame(
        report_values,
        columns=report_columns
    )

    # ---------------- Parameters sheet ---------------- #

    p_simulation = getattr(p.simulation.devices, device_key)

    param_columns = [
        "Number_of_devices",
        "sunrise_start",
        "sunrise_end",
        "sunset_start",
        "sunset_end",
        "interval_day_seconds",
        "interval_night_seconds",

        # --- Transmission base costs ---
        "max_KBs_per_message",
        "mqtt_cost_per_message_BRL",
        "connectivity_cost_per_minute_BRL",

        # --- Internet pricing (All) ---
        "internet_plan_Options",

        # --- Storage base costs ---
        "storage_cost_per_GB_BRL",
        "months_of_storage",
    ]

    param_values = [[
        len(df),
        daylight.sunrise_start,
        daylight.sunrise_end,
        daylight.sunset_start,
        daylight.sunset_end,
        p_simulation.publication_interval_day,
        p_simulation.publication_interval_night,

        # Transmission
        p_transmission.max_KBs_per_message,
        p_transmission.cost_per_mqtt_msg,
        p_transmission.connectivity_cost_per_minute,

        # Internet
        internet_princing,

        # Storage
        p_storage.storage_cost_per_GB,
        p_storage.months_of_storage
    ]]
    
    df_parameters = pd.DataFrame(
        param_values,
        columns=param_columns
    ).T.reset_index()
    df_parameters.columns = ["parameter", "value"]

    # ---------------- Write report file ---------------- #
    report_path = p.financial.general.save_report_path
    filename = f"{report_path}/storage_and_transmission_report_{device_key}.xlsx"
    with pd.ExcelWriter(
        filename,
        mode="w",
        engine="openpyxl"
    ) as writer:

        df_report.to_excel(
            writer,
            sheet_name="Report",
            index=False
        )

        df_parameters.to_excel(
            writer,
            sheet_name="Parameters",
            index=False
        )


    return df_report

# Legacy function kept for reference only
# def update_report(report, device_fin, transmission_size, storage_size, current_timestamp, is_fail):
    
#     # p is either FinancialPanelConfig or FinancialEdgeFogConfig
#     active_comm = device_fin.active_communication
#     overhead = active_comm.overhead_bytes if hasattr(active_comm, 'overhead_bytes') else 0
#     storage_price_per_MB = device_fin.storage_price_per_MB
#     transmission_price_MB = active_comm.transmission_price_MB if hasattr(active_comm, 'transmission_price_MB') else 0
    
#     transmission_MB = calculate_transmission_total_MB(transmission_size, overhead)
#     transmission_price = calculate_transmission_price_MB(transmission_MB, transmission_price_MB)
#     transmission_MB_with_failure = calculate_transmission_total_MB_with_failure(transmission_size, overhead, is_fail)
#     transmission_price_with_failure = calculate_transmission_price_MB(transmission_MB_with_failure, transmission_price_MB)
#     storage_MB = calculate_storage_total_MB(storage_size, is_fail)
#     storage_price = calculate_storage_price_MB(storage_MB, storage_price_per_MB)
    
#     report.append([current_timestamp, transmission_MB, float(transmission_MB_with_failure), float(transmission_price),
#                     float(transmission_price_with_failure), float(np.mean(is_fail)), float(storage_MB), float(storage_price)])
    
#     return report

#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------After Simulation----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# legacy functions kept for reference only
# def calculate_transmission_total_MB(byte_sizes, overhead):
    
#     number_of_messages = len(byte_sizes)
        
#     # Sum of transmitted bytes (payload)
#     total_payload_bytes = sum(byte_sizes)
        
#     # Total overhead (overhead_per_message * number of messages)
#     total_overhead_bytes = number_of_messages * overhead
        
#     # Add payload and overhead
#     total_bytes = total_payload_bytes + total_overhead_bytes
    
#     total_MB= round(total_bytes/1048576, 3)
        
#     return total_MB

# legacy function kept for reference only
# def calculate_transmission_total_MB_with_failure(byte_sizes, overhead, is_fail):
    
#     number_of_messages = sum(~is_fail)
        
#     # Sum of transmitted bytes (payload)
#     total_payload_bytes = sum(byte_sizes * (~is_fail))
        
#     # Total overhead (overhead_per_message * number of messages)
#     total_overhead_bytes = number_of_messages * overhead
        
#     # Add payload and overhead
#     total_bytes = total_payload_bytes + total_overhead_bytes
    
#     total_MB= round(total_bytes/1048576, 3)
        
#     return total_MB

# legacy function kept for reference only
# def calculate_storage_total_MB(byte_sizes, is_fail):
    
#     # Sum of transmitted bytes (payload)
#     total_bytes = sum(byte_sizes * (~is_fail))
        
#     total_MB= round(total_bytes/1048576, 3)
        
#     return total_MB

# legacy function kept for reference only
# def calculate_storage_price_MB(total_MB, storage_price_MB):
    
#     total_price = total_MB * storage_price_MB
    
#     return total_price

# legacy function kept for reference only
# def calculate_transmission_price_MB(total_MB, transmission_price_MB):
    
#     total_price = total_MB * transmission_price_MB
    
#     return total_price



#--------------------------------------------------------------------------------------------------------------------------------------------------------       


# legacy function kept for reference only
# def save_report(
#     report: list,
#     units: int,
#     count_iterations: int,
#     params,
#     total_time_simulation: float,
#     target: Literal["panel", "edge_fog"],
# ) -> None:

#     # ---------------- Common report ---------------- #

#     report_columns = [
#         "Date_time",
#         "Total_MB",
#         "Total_MB_with_failure",
#         "Total_price",
#         "Total_price_with_failure",
#         "Failure_rate",
#         "Total_storage_MB",
#         "Total_storage_price",
#     ]

#     df_report = pd.DataFrame(report, columns=report_columns)

#     # ---------------- Simulation time window ---------------- #

#     window = params.simulation.window
#     tz = pytz.timezone(window.time_zone)

#     start_dt = tz.localize(
#         datetime.combine(window.simulation_start_date, window.simulation_start_time)
#     )
#     end_dt = tz.localize(
#         datetime.combine(window.simulation_stop_date, window.simulation_stop_time)
#     )

#     summary_time = (
#         f"{start_dt.strftime('%m-%d-%Y %H-%M-%S')} "
#         f"to {end_dt.strftime('%m-%d-%Y %H-%M-%S')}"
#     )

#     # Ensure datetimes are timezone-unaware (Excel doesn't support tz-aware datetimes)
#     if "Date_time" in df_report.columns:
#         def _make_naive(x):
#             try:
#                 if isinstance(x, pd.Timestamp):
#                     if x.tzinfo is not None:
#                         return x.tz_convert(None)
#                     return x
#                 if isinstance(x, datetime):
#                     if x.tzinfo is not None:
#                         return x.replace(tzinfo=None)
#                     return x
#             except Exception:
#                 pass
#             return x

#         df_report["Date_time"] = df_report["Date_time"].apply(_make_naive)

    
#     # Some parameter structures store devices under `params.financial.devices`.
#     # Use that when available, otherwise fallback to `params.financial`.
#     financial_source = params.financial.devices
#     financial_target = getattr(financial_source, target)
#     report_path = financial_target.communication_cost_report.path

#     filename = f"{report_path}/data_report_{target}_{summary_time}.xlsx"

#     # ---------------- Write main report ---------------- #

#     with pd.ExcelWriter(filename, mode="w", engine="openpyxl") as writer:
#         df_report.to_excel(
#             writer,
#             sheet_name="Data Usage",
#             index=False,
#             header=True,
#         )

#     # ---------------- Parameters sheet ---------------- #

#     daylight = params.daylight
#     p_simulation = getattr(params.simulation.devices, target)

#     param_columns = [
#         "Number_of_devices",
#         "iterations",
#         "Simulation_duration",
#         "sunrise_start",
#         "sunrise_end",
#         "sunset_start",
#         "sunset_end",
#         "interval_day",
#         "interval_night",
#     ]

#     param_values = [[
#         units,
#         count_iterations,
#         total_time_simulation,
#         daylight.sunrise_start,
#         daylight.sunrise_end,
#         daylight.sunset_start,
#         daylight.sunset_end,
#         p_simulation.publication_interval_day,
#         p_simulation.publication_interval_night,
#     ]]


#     df_params = pd.DataFrame(param_values, columns=param_columns)

#     with pd.ExcelWriter(filename, mode="a", engine="openpyxl") as writer:
#         df_params.to_excel(
#             writer,
#             sheet_name="Parameters",
#             index=False,
#             header=True,
#         )

# legacy function kept for reference only
# def generate_summary_report(
#     report: list,
#     target: str,
#     params,
# ) -> pd.DataFrame:

#     columns = [
#         "Date_time",
#         "Total_MB",
#         "Total_MB_with_failure",
#         "Total_price",
#         "Total_price_with_failure",
#         "Failure_rate",
#         "Total_storage_MB",
#         "Total_storage_price",
#     ]

#     df = pd.DataFrame(report, columns=columns)

#     # ---- garantir datetime ----
#     df["Date_time"] = pd.to_datetime(
#         df["Date_time"],
#         format="%m-%d-%Y %H:%M:%S",
#     )

#     # ---- intervalo da simulação ----
#     start_time = df["Date_time"].min()
#     end_time = df["Date_time"].max()

#     summary_time = (
#         f"{start_time.strftime('%m-%d-%Y %H:%M:%S')} "
#         f"to {end_time.strftime('%m-%d-%Y %H:%M:%S')}"
#     )

#     filename_time = summary_time.replace(":", "-")

#     # ---- agregação ----
#     numeric_columns = df.columns.drop("Date_time")
#     summed_values = df[numeric_columns].sum()

#     summary_df = pd.DataFrame([summed_values])
#     summary_df.insert(0, "Date_time", summary_time)

#     # ---- persistência ----
#     financial_target = getattr(params.financial.devices, target)
#     report_path = financial_target.communication_cost_report.path
#     filename = f"{report_path}/summary_report_{target}_{filename_time}.xlsx"

#     summary_df.to_excel(
#         filename,
#         sheet_name="Data Usage",
#         index=False,
#         float_format="%.2f",
#         engine="openpyxl",
#     )

#     return summary_df
