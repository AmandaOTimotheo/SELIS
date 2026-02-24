"""Energy consumption and cost analysis helpers for simulation outputs."""

from datetime import datetime as dt
from pathlib import Path
import re
from typing import Literal

import matplotlib.pyplot as plt
from matplotlib.patheffects import withStroke
import pandas as pd


def update_consumption(
    params,
    report_consumption: list,
    df_data,
    current_timestamp,
    target: Literal["panel", "edge_fog"],
) -> list:
    """Aggregate consumption values and append tariff costs for one timestamp."""

    # Unit energy price.
    price_kwh = params.financial.general.price_kWh

    # Consumption key used in payload headers.
    payload = getattr(params.financial.devices, target).payloads
    header_consumption = payload.header.measures.consumption  # Example: "EN"

    # Match both edge (EN) and panel (EN1, EN2, ...) consumption columns.
    pattern = re.compile(rf"^{header_consumption}(\d{{1,2}})?$")

    consumption_sum = 0.0

    for col in df_data.columns:
        if pattern.match(col):
            consumption_sum += df_data[col].sum()

    # Tariff cost calculations.
    add_cost_100kwh = params.financial.general.estimated_vs_simulated
    cost_green_flag = consumption_sum * price_kwh
    cost_yellow_flag = consumption_sum / 100 * (price_kwh * 100 + add_cost_100kwh.yellow_flag_add_price)
    cost_red_flag_1 = consumption_sum / 100 * (price_kwh * 100 + add_cost_100kwh.red_flag_1_add_price)
    cost_red_flag_2 = consumption_sum / 100 * (price_kwh * 100 + add_cost_100kwh.red_flag_2_add_price)
    report_consumption.append(
        [current_timestamp, consumption_sum, cost_green_flag, cost_yellow_flag, cost_red_flag_1, cost_red_flag_2]
    )

    return report_consumption

def save_consumption_report(
    report_consumption: list,
    p,
    target: Literal["panel", "edge_fog"],
) -> None:
    """Persist simulated consumption data to an Excel report per device type."""

    # ---------------- DataFrame ---------------- #

    report_columns = ["Date_time", "Consumption", "Cost_green_flag", "Cost_yellow_flag", "Cost_red_flag_1", "Cost_red_flag_2"]
    df = pd.DataFrame(report_consumption, columns=report_columns)

    # Excel does not support timezone-aware datetimes; strip tzinfo without shifting clock time
    if "Date_time" in df.columns:
        def _make_naive(x):
            try:
                if isinstance(x, pd.Timestamp):
                    if x.tzinfo is not None:
                        return x.tz_localize(None)
                    return x
                if isinstance(x, dt):
                    if x.tzinfo is not None:
                        return x.replace(tzinfo=None)
                    return x
            except Exception:
                pass
            return x

        df["Date_time"] = df["Date_time"].apply(_make_naive)

    # ---------------- Report path ---------------- #

    report_path = p.financial.general.save_report_path

    filename = f"{report_path}/consumption_report_{target}.xlsx"

    # ---------------- Save ---------------- #
    with pd.ExcelWriter(filename, mode="w", engine="openpyxl") as writer:
        df.to_excel(
            writer,
            sheet_name="Consumption",
            index=False,
            header=True,
        )




def calculate_simulated_measure(p):
    """Read simulated reports and compute total energy plus tariff costs."""
    report_path = Path(p.financial.general.save_report_path)

    dfs = []
    targets = []

    # ---------------- Load enabled devices dynamically ---------------- #
    for device_name in type(p.simulation.devices).model_fields.keys():
        device_fin = getattr(p.financial.devices, device_name)


        if not device_fin.communication_cost_report.enable_consumption_report:
            continue

        report_file = report_path / f"consumption_report_{device_name}.xlsx"

        if not report_file.exists():
            raise FileNotFoundError(
                f"Consumption report not found for device '{device_name}': {report_file}"
            )

        df = pd.read_excel(report_file)
        dfs.append(df)
        targets.append(device_name.replace("_", " ").title())

    if not dfs:
        raise RuntimeError("No enabled devices with consumption reports found.")

    # ---------------- Aggregate ---------------- #
    df_all = pd.concat(dfs, ignore_index=True)

    energy_kwh = df_all["Consumption"].sum()

    costs = {
        "green": df_all["Cost_green_flag"].sum(),
        "yellow": df_all["Cost_yellow_flag"].sum(),
        "red_1": df_all["Cost_red_flag_1"].sum(),
        "red_2": df_all["Cost_red_flag_2"].sum(),
    }

    # ---------------- Simulation window ---------------- #
    window = p.simulation.window
    start_time = dt.combine(window.simulation_start_date, window.simulation_start_time)
    end_time = dt.combine(window.simulation_stop_date, window.simulation_stop_time)

    summary_time = (
        f"{start_time.strftime('%m-%d-%Y %H:%M:%S')} "
        f"to {end_time.strftime('%m-%d-%Y %H:%M:%S')}"
    )

    # ---------------- Output ---------------- #
    targets_label = " and ".join(targets)

    is_brl = p.financial.general.currency_code == "BRL"
    currency_symbol = p.financial.general.currency_symbol
    print(
        f"\nSimulated consumption: {fmt_energy(energy_kwh, is_brl)} kWh "
        f"from {summary_time} connected to {targets_label}."
    )
    print(f"Base price per kWh in {currency_symbol}: {p.financial.general.price_kWh:.2f}\n")

    print("Simulated cost by tariff flag:")
    print(f"Green:   {currency_symbol} {fmt_money(costs['green'], is_brl)}")
    print(f"Yellow:  {currency_symbol} {fmt_money(costs['yellow'], is_brl)}")
    print(f"Red 1:   {currency_symbol} {fmt_money(costs['red_1'], is_brl)}")
    print(f"Red 2:   {currency_symbol} {fmt_money(costs['red_2'], is_brl)}")
    print("\n" + "-" * 85)

    return (end_time-start_time).total_seconds()/3600, energy_kwh, costs


def calculate_estimated_measure(p, df_devices: list):
    """Estimate energy/cost from rated power and configured operating hours."""

    targets = []
    
    total_consumption = 0
    total_lightning_points = 0
    total_hours_on = calculate_total_hours_on(p)
    for device_name, df_device in df_devices:
        p_device = getattr(p.simulation.devices, device_name)
        device_fin = getattr(p.financial.devices, device_name)

        if not device_fin.communication_cost_report.enable_consumption_report:
            continue
        
        if df_device is None or df_device.empty:
            raise ValueError(f"No data available for {device_name}. Cannot calculate estimated consumption.")

        fields = p_device.database.fields
        targets.append(device_name.replace("_", " ").title())
                
        rated_power = df_device[fields.rated_power].to_numpy()  # in Watts
   
        total_consumption += sum(rated_power) * (total_hours_on / 1000)  # in kWh
        total_lightning_points += len(rated_power)

    price_kWh = p.financial.general.price_kWh
    add = p.financial.general.estimated_vs_simulated
    costs = {
        "green": total_consumption * price_kWh,
        "yellow": total_consumption * (price_kWh * 100 + add.yellow_flag_add_price) / 100,
        "red_1": total_consumption * (price_kWh * 100 + add.red_flag_1_add_price) / 100,
        "red_2": total_consumption * (price_kWh * 100 + add.red_flag_2_add_price) / 100
    }

    # ---------------- Simulation window ---------------- #
    window = p.simulation.window
    start_time = dt.combine(window.simulation_start_date, window.simulation_start_time)
    end_time = dt.combine(window.simulation_stop_date, window.simulation_stop_time)

    summary_time = (
        f"{start_time.strftime('%m-%d-%Y %H:%M:%S')} "
        f"to {end_time.strftime('%m-%d-%Y %H:%M:%S')}"
    )

    # ---------------- Output ---------------- #
    targets_label = " and ".join(targets)

    is_brl = p.financial.general.currency_code == "BRL"
    currency_symbol = p.financial.general.currency_symbol
    print(
        f"\nEstimated consumption: {fmt_energy(total_consumption, is_brl)} kWh "
        f"from {summary_time} connected to {targets_label}."
    )
    print(f"Base price per kWh in {currency_symbol}: {price_kWh:.2f}\n")

    print("Estimated cost by tariff flag:")
    print(f"Green:   {currency_symbol} {fmt_money(costs['green'], is_brl)}")
    print(f"Yellow:  {currency_symbol} {fmt_money(costs['yellow'], is_brl)}")
    print(f"Red 1:   {currency_symbol} {fmt_money(costs['red_1'], is_brl)}")
    print(f"Red 2:   {currency_symbol} {fmt_money(costs['red_2'], is_brl)}")
    print("\n" + "-" * 85)
         
    return total_lightning_points, total_consumption, costs


# Formatting helpers.
def fmt_money(v, is_brl: bool) -> str:
    """Format currency values according to the configured locale convention."""
    if not is_brl:
        return f"{v:,.2f}"
    return f"{v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def fmt_energy(v, is_brl: bool) -> str:
    """Format energy values according to the configured locale convention."""
    if not is_brl:
        return f"{v:,.2f}"
    return f"{v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def calculate_total_hours_on(p):
    """Estimate total ON hours for the simulation window."""
    estimated_hours_on_per_day = (
        p.financial.general.estimated_vs_simulated.estimated_hours_on_per_day
    )

    start_dt = dt.combine(p.simulation.window.simulation_start_date, p.simulation.window.simulation_start_time)
    end_dt = dt.combine(p.simulation.window.simulation_stop_date, p.simulation.window.simulation_stop_time)

    total_simulation_hours = (end_dt - start_dt).total_seconds() / 3600
    tolerance_hours = 5 / 60  # 5 minutes
    if total_simulation_hours <= 0 or abs(total_simulation_hours % 24) > tolerance_hours:
        print(
            "Warning: For accurate estimated vs simulated comparison, use full 24-hour simulation windows. "
            f"Current window is {total_simulation_hours:.2f} hours."
        )

    total_hours_on = total_simulation_hours * (estimated_hours_on_per_day / 24)

    return total_hours_on

def analysis_estimated_vs_simulated(p, df_devices: list):
    """Generate console summary and plots for estimated vs simulated costs."""
    
    
    total_lightning_points,total_energy_estimated, results_estimated = calculate_estimated_measure(p, df_devices)
    total_hours_simulated, total_energy_simulated, results_simulated = calculate_simulated_measure(p)
          
    start_dt = dt.combine(p.simulation.window.simulation_start_date, p.simulation.window.simulation_start_time)
    end_dt = dt.combine(p.simulation.window.simulation_stop_date, p.simulation.window.simulation_stop_time)
    
    diff_total_energy = total_energy_estimated - total_energy_simulated
    
    if total_energy_estimated == 0:
        percentage_diff = 0
    else:
        percentage_diff = (diff_total_energy / total_energy_estimated) * 100
    
    diff_results_estimated_green = results_estimated['green'] - results_simulated['green']
    diff_results_estimated_yellow = results_estimated['yellow'] - results_simulated['yellow']
    diff_results_estimated_red_1 = results_estimated['red_1'] - results_simulated['red_1']
    diff_results_estimated_red_2 = results_estimated['red_2'] - results_simulated['red_2']
    
    is_brl = p.financial.general.currency_code == "BRL"
    display_diff_green = fmt_money(diff_results_estimated_green, is_brl)
    display_diff_yellow = fmt_money(diff_results_estimated_yellow, is_brl)
    display_diff_red_1 = fmt_money(diff_results_estimated_red_1, is_brl)
    display_diff_red_2 = fmt_money(diff_results_estimated_red_2, is_brl)
    
    # Daily per-lighting-point energy comparison.
    hours_per_day_estimated = (
        p.financial.general.estimated_vs_simulated.estimated_hours_on_per_day
    )
    
    sunrise_start = p.simulation.daylight.sunrise_start
    sunset_end = p.simulation.daylight.sunset_end
    sun_duration = dt.combine(dt.today(), sunset_end) - dt.combine(dt.today(), sunrise_start)
    night_seconds = (24 * 3600) - sun_duration.seconds
    night_minutes = night_seconds // 60
        
    hours_per_day_simulated = night_minutes / 60
    
    approx_energy_per_day_estimated = total_energy_estimated / total_hours_simulated * 24
    approx_energy_per_day_simulated = total_energy_simulated / total_hours_simulated * 24
    
    daily_consumption_per_point_estimated = approx_energy_per_day_estimated/total_lightning_points
    daily_consumption_per_point_simulated = approx_energy_per_day_simulated/total_lightning_points

    print(f"\nFor {total_lightning_points} lighting points:")
    print(f"The estimated consumed energy is {diff_total_energy}(kWh) higher than the simulated.")
    print(f"Therefore... the economy produced between {start_dt} to {end_dt} is:")
    currency_symbol = p.financial.general.currency_symbol
    print(f"Green:   {currency_symbol} {display_diff_green}")
    print(f"Yellow:  {currency_symbol} {display_diff_yellow}")
    print(f"Red 1:   {currency_symbol} {display_diff_red_1}")
    print(f"Red 2:   {currency_symbol} {display_diff_red_2}\n")
    print(f"Which represents {percentage_diff:.2f} %")
    print(f"(Daily estimated consumption per lighting point of approx. {daily_consumption_per_point_estimated:.2f}kWh against {daily_consumption_per_point_simulated:.2f}kWh for the simulated.)")
    
    currency_code = p.financial.general.currency_code
    currency_symbol = p.financial.general.currency_symbol
    is_brl = currency_code == "BRL"

    generate_comparison_bargraph(
        p,
        results_estimated,
        results_simulated,
        start_dt,
        end_dt,
        currency_code,
        currency_symbol,
        is_brl,
    )
    generate_projection_timeframe(
        p,
        approx_energy_per_day_estimated,
        approx_energy_per_day_simulated,
        currency_code,
        currency_symbol,
        is_brl,
    )
    
def generate_comparison_bargraph(
    p,
    results_estimated,
    results_simulated,
    start_dt,
    end_dt,
    currency_code: str,
    currency_symbol: str,
    is_brl: bool,
):
    """Create and save estimated-vs-simulated tariff bar chart."""

    # Define tariff flag labels and values
    labels = ['Green', 'Yellow', 'Red 1', 'Red 2']
    estimated_values = [
        results_estimated['green'],
        results_estimated['yellow'],
        results_estimated['red_1'],
        results_estimated['red_2']
    ]
    simulated_values = [
        results_simulated['green'],
        results_simulated['yellow'],
        results_simulated['red_1'],
        results_simulated['red_2']
    ]

    # Calculate deltas for label display
    deltas = [e - s for e, s in zip(estimated_values, simulated_values)]

    # Bar positions and width
    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots()

    # Create bars for estimated and simulated values with distinct colors
    bars1 = ax.bar([i - width/2 for i in x], estimated_values, width, label='Estimated', color='#C0392B')  # dark red
    bars2 = ax.bar([i + width/2 for i in x], simulated_values, width, label='Simulated', color='#27AE60')  # dark green

    # Set chart title and axis labels
    ax.set_ylabel(f"Cost ({currency_symbol})")
    sim_period = f"{start_dt.strftime('%m/%d/%Y %H:%M')} to {end_dt.strftime('%m/%d/%Y %H:%M')}"
    ax.set_title(f'Estimated vs Simulated Costs by Tariff Flag\n({sim_period})', pad=20)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)

    def format_money(value, decimals=0):
        formatted = f"{value:,.{decimals}f}"
        if not is_brl:
            return formatted
        return formatted.replace(",", "v").replace(".", ",").replace("v", ".")

    # Add deltas below tick labels
    for i, delta in enumerate(deltas):
        delta_label = f"Delta {format_money(delta, 0)}"
        ax.annotate(delta_label,
                    xy=(i, 0),
                    xytext=(0, -20),
                    textcoords='offset points',
                    ha='center', va='top',
                    fontsize=12, fontweight='bold')

    # Applying formatting to thousands on the Y-axis
    ax.ticklabel_format(axis='y', style='sci', scilimits=(3,3))
    ax.yaxis.get_offset_text().set_fontsize(8)

    # Add grid lines
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.xaxis.grid(False)

    # Remove top and right borders
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Position the legend below the chart
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)

    # Add value labels above each bar
    def add_labels(bars):
        for bar in bars:
            height = bar.get_height()
            label_value = height / 1000  # Divide by 1e3
            ax.annotate(format_money(label_value, 1),
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=10, fontweight='bold')

    add_labels(bars1)
    add_labels(bars2)
    
    plt.tight_layout()
    
    # Save the figure
    
    suffix = "" if is_brl else f"_{currency_code.lower()}"
    fin_path = f"{p.financial.general.save_report_path}/tariff_comparison_bargraph{suffix}.png"

    plt.savefig(fin_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\nComparison bar graph saved to {fin_path}")
def generate_projection_timeframe(
    p,
    approx_energy_per_day_estimated,
    approx_energy_per_day_simulated,
    currency_code: str,
    currency_symbol: str,
    is_brl: bool,
):
    """Create and save long-range cost projection charts and CSV summary."""
    

    total_estimated_cost_daily = approx_energy_per_day_estimated * p.financial.general.price_kWh
    total_simulated_cost_daily = approx_energy_per_day_simulated * p.financial.general.price_kWh

        
    # Define the timeframes for projection
    timeframes_days = {
        "1 Day": 1,
        "1 Week": 7,
        "1 Month": 30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year": 365
    }

    # Prepare data for DataFrame
    data = []
    for label, days in timeframes_days.items():
        estimated = total_estimated_cost_daily * days
        simulated = total_simulated_cost_daily * days
        delta = estimated - simulated
        percent = (delta / estimated * 100) if estimated else 0

        data.append({
            "Period": label,
            "Estimated": round(estimated, 2),
            "Simulated": round(simulated, 2),
            "Difference": round(delta, 2),
            "Difference (%)": round(percent, 2)
        })

    # Create DataFrame
    df = pd.DataFrame(data)

    # Plot the summary
    labels = df["Period"].tolist()
    estimated = df["Estimated"].tolist()
    simulated = df["Simulated"].tolist()
    deltas = df["Difference"].tolist()
    x = range(len(labels))
    text_outline = [withStroke(linewidth=3, foreground='white')]

    # Build x-axis labels with deltas, with extra spacing
    #x_labels = [f"{label}\nDelta {delta:,.0f}".replace(",", "v").replace(".", ",").replace("v", ".")
    #            for label, delta in zip(labels, deltas)]

    fig, ax = plt.subplots(figsize=(14, 8))  # Increase size for more space
    ax.plot(x, estimated, label="Estimated", color='#C0392B', marker='o', linewidth=2)
    ax.plot(x, simulated, label="Simulated", color='#27AE60', marker='o', linewidth=2)

    def format_money(value, decimals=0):
        formatted = f"{value:,.{decimals}f}"
        if not is_brl:
            return formatted
        return formatted.replace(",", "v").replace(".", ",").replace("v", ".")

    for i in x:
        ax.text(i, estimated[i] + (max(estimated) * 0.02),
            format_money(estimated[i], 0),
                fontsize=13, fontweight='bold', color='#C0392B', ha='center', path_effects=text_outline)
        ax.text(i, simulated[i] - (max(simulated) * 0.035),
            format_money(simulated[i], 0),
                fontsize=13, fontweight='bold', color='#27AE60', ha='center', path_effects=text_outline)

    ax.set_xticks(list(x))
    #ax.set_xticklabels(x_labels, fontsize=10)
    ax.set_xticklabels(labels, fontsize=12)

    # Add deltas below tick labels
    for i, delta in enumerate(deltas):
        delta_label = f"Delta {format_money(delta, 0)}"
        ax.annotate(delta_label,
                    xy=(i, 0),
                    xytext=(0, -45),
                    textcoords='offset points',
                    ha='center', va='top',
                    fontsize=13, fontweight='bold')

    ax.set_title("Cost Projection - Estimated vs Simulated", pad=25)
    ax.set_xlabel("Period", labelpad=18, fontsize=13)
    ax.set_ylabel(f"Cumulative Value ({currency_symbol})", labelpad=10, fontsize=13)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(fontsize=13)
    plt.tight_layout()
    suffix = "" if is_brl else f"_{currency_code.lower()}"
    fin_path = f"{p.financial.general.save_report_path}/projection_timeframe{suffix}"
    
    plt.savefig(fin_path+".png", dpi=300, bbox_inches='tight')
    plt.show()

    df.to_csv(fin_path + ".csv", index=False)

    print(f"\nProjection timeframe graph saved to {fin_path}.png")
    print(f"Projection timeframe data saved to {fin_path}.csv")
