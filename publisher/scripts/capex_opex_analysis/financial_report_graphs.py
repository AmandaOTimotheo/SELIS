import debugpy
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

#----------------------------------------------------------------------------------------------------
# Panel Graphs


def format_currency(value, currency_symbol):
    formatted = f"{currency_symbol} {value:,.0f}"
    if currency_symbol == "US$":
        return formatted
    return formatted.replace(",", ".")


def capex_bar_graph(
    df,
    *,
    capex_keys,
    label_map_grouped,
    colors,
    title,
    currency_symbol,
    filename,
    total_box_edgecolor='gray',
    fig_size=(8, 6)
):
    df_capex = df[df["Variables"].isin(capex_keys)].copy()

    grouped_values = {
        label: df_capex[df_capex["Variables"].isin(keys)]["Values"].sum()
        for label, keys in label_map_grouped.items()
    }

    labels = list(grouped_values.keys())
    values = list(grouped_values.values())

    total_value = sum(values)
    total_label = f"Total: {format_currency(total_value, currency_symbol)}"

    fig, ax = plt.subplots(figsize=fig_size)

    bars = ax.bar(labels, values, color=colors)

    for bar, value in zip(bars, values):
        percentage = (value / total_value) * 100 if total_value else 0
        value_label = format_currency(value, currency_symbol)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value_label}\n({percentage:.2f}%)",
            ha='center',
            va='bottom',
            fontsize=16,
            fontweight='bold'
        )

    # --- Axis styling ---
    ax.set_ylabel(f"Cost ({currency_symbol})", fontsize=16)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ax.tick_params(axis='x', labelsize=16)
    ax.tick_params(axis='y', labelsize=16)

    # --- Reserve space at top ---
    fig.subplots_adjust(
        top=0.78,
        left=0.14   # ← espaço para o ylabel
    )

    # --- Title (figure-level) ---
    fig.suptitle(title, fontsize=16, y=0.95)

    # --- Total (always below title, never overlapping) ---
    fig.text(
        0.5,
        0.89,
        total_label,
        ha='center',
        va='top',
        fontsize=16,
        fontweight='bold',
        bbox=dict(
            facecolor='white',
            edgecolor=total_box_edgecolor,
            boxstyle='round,pad=0.4'
        )
    )

    fig.savefig(filename, dpi=300)
    plt.close(fig)




def opex_pie_graph(
    df,
    *,
    opex_keys,
    label_map,
    color_map,
    title,
    currency_symbol,
    filename,
    total_box_edgecolor='gray',
    fig_size=(6, 6),
    startangle=90,
    labeldistance=1.10
):
    df_opex = df[df["Variables"].isin(opex_keys)].copy()
    df_opex["Label"] = df_opex["Variables"].map(label_map)
    df_opex["Color"] = df_opex["Label"].map(color_map)

    values = df_opex["Values"].tolist()
    labels = df_opex["Label"].tolist()
    colors = df_opex["Color"].tolist()

    total_value = sum(values)
    total_label = f"Total: {format_currency(total_value, currency_symbol)}"

    fig, ax = plt.subplots(figsize=fig_size)

    def autopct(pct):
        value = pct * total_value / 100
        return f"{pct:.2f}%\n({format_currency(value, currency_symbol)})"

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct=autopct,
        startangle=startangle,
        labeldistance=labeldistance,
        wedgeprops=dict(edgecolor='white'),
        textprops=dict(color='black', fontsize=14)
    )

    for autotext in autotexts:
        autotext.set_fontweight('bold')
        autotext.set_fontsize(13)

    # --- Reserve space at top ---
    fig.subplots_adjust(top=0.78)

    # --- Title ---
    fig.suptitle(title, fontsize=16, y=0.95)

    # --- Total (always below title, never overlapping) ---
    fig.text(
        0.5,
        0.89,
        total_label,
        ha='center',
        va='top',
        fontsize=15,
        fontweight='bold',
        bbox=dict(
            facecolor='white',
            edgecolor=total_box_edgecolor,
            boxstyle='round,pad=0.3'
        )
    )

    fig.savefig(filename, dpi=300)
    plt.close(fig)






