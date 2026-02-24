import debugpy
import pandas as pd
import plotly.io as pio
from plotly.subplots import make_subplots
import plotly.graph_objects as go

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------Panel Dashboard--------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
import numpy as np
import pandas as pd


def generate_general_dashboard_with_currency(
    p,
    df_devices: list,
    device_reports: list
    ):
  
    if any(df_device is None or df_device.empty for _, df_device in df_devices):
        print("Warning: One or more device dataframes are empty or None. The dashboard can't be generated without device data. Please check the input dataframes.")
        return
    """
    Wrapper that:
    1) Uses already-converted report dataframes from Pydantic
    2) Calls create_general_dashboard (which uses render(model) to set currency dynamically)
    """
    # Procura pelo device name = "panel" e puxa o report
    panel_report_data = next((report for name, report in device_reports if name == "panel"), None)
    edge_fog_report_data = next((report for name, report in device_reports if name == "edge_fog"), None)
    df_panels = next((df for name, df in df_devices if name == "panel"), pd.DataFrame())
    df_edges = next((df for name, df in df_devices if name == "edge_fog"), pd.DataFrame())

    p_gen = p.financial.general
    create_general_dashboard(
        df_panels=df_panels,
        df_edges=df_edges,
        panel_report_data=panel_report_data,
        Edge_fog_report_data=edge_fog_report_data,
        currency_symbol=p_gen.currency_symbol,
        currency_locale=p_gen.currency_locale,
        file_path=p_gen.save_report_path,
    )


import debugpy

def create_general_dashboard(
    df_panels,
    df_edges,
    panel_report_data,
    Edge_fog_report_data,
    currency_symbol: str,
    currency_locale: str,
    file_path: str,
):
    html_code = f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Dashboard – Panel vs Edge/Fog</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

<style>
:root{{
  --bg:#f4f4f5; --card:#ffffff; --ink:#111827; --muted:#6b7280;
  --blue-1:#0051ff; --blue-2:#a6ceff; --blue-3:#3A689C; --blue-4:#000d30;
  --gray-1:#111827; --gray-2:#6b7280; --gray-3:#9ca3af; --gray-4:#d1d5db;
  --yellow:#fef3c7;
  --border:#e5e7eb; --shadow:0 10px 20px rgba(0,0,0,.06);
}}
*{{box-sizing:border-box}}
canvas {{
  width: 100% !important;
  height: 300px !important;
}}
#opexPanelPie, #opexEdgePie {{
  width: 100% !important;
  height: 300px !important;
}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial}}
.wrap{{max-width:1600px;margin:24px auto;padding:0 32px}}
h1 {{
  text-align: center;
  background: linear-gradient(90deg, #eeeeee, #ffffff);
  color: black;
  padding: 6px;
  border-radius: 12px;
  font-size: 36px;
  font-weight: 800;
  box-shadow: 0 4px 12px rgba(0,0,0,.2);
  margin: 0 auto 24px;
  max-width: 900px;
}}

.grid {{ display:grid; grid-template-columns:1fr; gap:16px; }}
.boards{{
  display:grid; gap:16px;
  grid-template-columns:repeat(3,1fr);
}}
.card{{
  background:var(--card); border:1px solid var(--border); border-radius:12px;
  box-shadow:var(--shadow); padding:14px; display:flex; flex-direction:column; min-height:280px
}}
.card h3{{font-size:22px;margin:0 0 8px}}
.total-badge{{
  font-weight:700; background:#eef2ff; border:1px solid #c7d2fe; color:#1e3a8a;
  padding:4px 8px; border-radius:8px; display:inline-block; margin-bottom:8px
}}
.pill{{
  border-radius:12px; padding:14px; font-weight:800; box-shadow:var(--shadow);
}}
.pill.yellow{{background:var(--yellow)}}
.pill.blue{{background:#dbeafe}}
.pill.gray{{background:#e5e7eb}}
.kpi{{display:grid; gap:14px}}
.kpi .line{{display:flex; align-items:center; gap:10px; justify-content:space-between}}
.big{{font-size:20px}}
.mid{{font-size:16px}}
@media (max-width:1024px){{
  .grid{{grid-template-columns:1fr}}
  h1{{writing-mode:horizontal-tb; transform:none; font-size:28px; margin:0}}
  .boards{{grid-template-columns:repeat(2,1fr)}}
}}
@media (max-width:640px){{
  .boards{{grid-template-columns:1fr}}
}}
canvas{{max-height:300px}}
</style>
</head>

<body>
<div class="wrap">
  <div class="topbar">
    <h1>Dashboard – Panel vs Edge/Fog</h1>
  </div>

  <div class="grid">
    <div class="boards">
      <section class="card">
        <h3>Opex Components – Panel-based system</h3>
        <span id="opexPanelTotal" class="total-badge">Total: 0</span>
        <canvas id="opexPanelPie" aria-label="Opex Panel Pie"></canvas>
      </section>

      <section class="card">
        <h3>Capex Components – Panel-based system</h3>
        <span id="capexPanelTotal" class="total-badge">Total: 0</span>
        <canvas id="capexPanelBar" aria-label="Capex Panel Bar"></canvas>
      </section>

      <section class="card">
        <h3>Overview</h3>
        <div class="kpi">
          <div class="pill yellow line">
            <div><span id="kpiTotal" class="big">0</span> <span class="mid">Streetlights</span></div>
          </div>
          <div class="pill blue line">
            <div><span id="kpiEdge" class="big">0</span> <span class="mid">in Edge/Fog</span></div>
            <div class="big" id="kpiEdgePct">0%</div>
          </div>
          <div class="pill gray line">
            <div><span id="kpiPanel" class="big">0</span> <span class="mid">in Panel</span></div>
            <div class="big" id="kpiPanelPct">0%</div>
          </div>
        </div>
      </section>

      <section class="card">
        <h3>Opex Components – Edge/Fog-based system</h3>
        <span id="opexEdgeTotal" class="total-badge">Total: 0</span>
        <canvas id="opexEdgePie" aria-label="Opex Edge Pie"></canvas>
      </section>

      <section class="card">
        <h3>Capex Components – Edge/Fog-based system</h3>
        <span id="capexEdgeTotal" class="total-badge">Total: 0</span>
        <canvas id="capexEdgeBar" aria-label="Capex Edge Bar"></canvas>
      </section>

      <section class="card">
        <h3>Capex + Opex</h3>
        <div class="kpi">
          <div class="pill gray line">
            <div><span id="miPanelText" class="big">0</span> <span class="mid">in Panel</span></div>
          </div>
          <div class="pill blue line">
            <div><span id="miEdgeText" class="big">0</span> <span class="mid">in Edge/Fog</span></div>
          </div>
          <div class="pill yellow line">
            <div><span id="miTotalText" class="big">0</span> <span class="mid">in Total</span></div>
          </div>
        </div>
      </section>
    </div>
  </div>
</div>

<script>
// Fixed color palettes
const COLORS = {{
  panelPie:   ["#606060","#949494"],
  edgePie:    ["#9ECAE1","#2171B5","#C6DBEF","#6BAED6"],
  panelBars:  ["#949494","#606060"],
  edgeBars:   ["#2171B5","#6BAED6"],
}};

const sum = (arr) => arr.reduce((a,b)=>a+(+b||0),0);

let charts = {{}};
function destroyCharts() {{
  Object.values(charts).forEach(c => c?.destroy());
  charts = {{}};
}}

function render(model) {{
  // Currency config must come exclusively from the model
  const CURRENCY = {{
    symbol: model.currencySymbol || "",
    locale: model.currencyLocale || "en-US"
  }};

  const isUSD = CURRENCY.symbol === "US$";

  // Integer formatter (used for counts)
  const fmtInt = (v) => {{
    if (!isFinite(v)) return "0";
    return new Intl.NumberFormat(CURRENCY.locale, {{ maximumFractionDigits: 0 }}).format(v);
  }};

  // Money formatter for card totals (no decimals)
  const fmtMoneyCard = (v) => {{
    if (!isFinite(v)) return "0";
    return new Intl.NumberFormat(CURRENCY.locale, {{ maximumFractionDigits: 0 }}).format(v);
  }};

  // Money formatter used in labels/tooltips (K/M suffix)
  const fmtMoneyShort = (v) => {{
    if (!isFinite(v)) return "0";
    if (isUSD) return new Intl.NumberFormat(CURRENCY.locale, {{maximumFractionDigits: 2}}).format(v);
    if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(2) + " M";
    if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(2) + " K";
    return new Intl.NumberFormat(CURRENCY.locale, {{maximumFractionDigits:2}}).format(v);
  }};

  const fmtMoneyLabel = (v) => {{
    if (!isFinite(v)) return "0";
    if (isUSD) return new Intl.NumberFormat(CURRENCY.locale, {{maximumFractionDigits: 0}}).format(v);
    if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(0) + " M";
    if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(0) + " K";
    return new Intl.NumberFormat(CURRENCY.locale, {{maximumFractionDigits:0}}).format(v);
  }};

  const total = +model.totalStreet || 0;
  const edge  = +model.edgeCount || 0;
  const panel = +model.panelCount || 0;
  const edgePct  = total ? (edge/total*100) : 0;
  const panelPct = total ? (panel/total*100) : 0;

  // KPIs (counts)
  document.getElementById("kpiTotal").textContent = fmtInt(total);
  document.getElementById("kpiEdge").textContent  = fmtInt(edge);
  document.getElementById("kpiPanel").textContent = fmtInt(panel);
  document.getElementById("kpiEdgePct").textContent  = edgePct.toFixed(0) + "%";
  document.getElementById("kpiPanelPct").textContent = panelPct.toFixed(0) + "%";

  const opexPanelData  = [ +model.opexPanelMaint||0, +model.opexPanelEnergy||0 ];
  const opexPanelTotal = sum(opexPanelData);
  document.getElementById("opexPanelTotal").textContent = `Total: ${{CURRENCY.symbol}} ${{fmtMoneyShort(opexPanelTotal)}}`;

  const opexEdgeData  = [ +model.opexEdgeEnergy||0, +model.opexEdgeMaint||0, +model.opexFogEnergy||0, +model.opexFogMaint||0 ];
  const opexEdgeTotal = sum(opexEdgeData);
  document.getElementById("opexEdgeTotal").textContent = `Total: ${{CURRENCY.symbol}} ${{fmtMoneyShort(opexEdgeTotal)}}`;

  const capexPanelData  = [ +model.capexPanelDevice||0, +model.capexCables||0 ];
  const capexPanelTotal = sum(capexPanelData);
  document.getElementById("capexPanelTotal").textContent = `Total: ${{CURRENCY.symbol}} ${{fmtMoneyShort(capexPanelTotal)}}`;

  const capexEdgeData  = [ +model.capexEdgeDevice||0, +model.capexFogDevice||0 ];
  const capexEdgeTotal = sum(capexEdgeData);
  document.getElementById("capexEdgeTotal").textContent = `Total: ${{CURRENCY.symbol}} ${{fmtMoneyShort(capexEdgeTotal)}}`;

  const miPanel = capexPanelTotal + opexPanelTotal;
  const miEdge  = capexEdgeTotal  + opexEdgeTotal;
  const miAll   = miPanel + miEdge;

  // Capex + Opex card texts
  document.getElementById("miPanelText").textContent = `${{CURRENCY.symbol}} ${{fmtMoneyCard(miPanel)}}`;
  document.getElementById("miEdgeText").textContent  = `${{CURRENCY.symbol}} ${{fmtMoneyCard(miEdge)}}`;
  document.getElementById("miTotalText").textContent = `${{CURRENCY.symbol}} ${{fmtMoneyCard(miAll)}}`;

  destroyCharts();

  charts.opexPanelPie = new Chart(document.getElementById("opexPanelPie"), {{
    type:"pie",
    data:{{ labels:["Panel Maintenance","Panel Energy"], datasets:[{{ data: opexPanelData, backgroundColor: COLORS.panelPie }}] }},
    options:{{
      layout: {{padding: {{ top: 0,right: 0,bottom: 25,left: 0}} }},
      maintainAspectRatio: false,
      responsive: true,
      plugins:{{
        legend:{{position:"bottom", labels: {{font: {{size: 16}} }}}},
        display: false,
        tooltip:{{callbacks:{{label:(ctx)=> `${{CURRENCY.symbol}} ${{fmtMoneyShort(ctx.raw)}}`}} }}
      }}
    }}
  }});

  charts.opexEdgePie = new Chart(document.getElementById("opexEdgePie"), {{
    type:"pie",
    data:{{ labels:["Edge Energy","Edge Maintenance","Fog Energy","Fog Maintenance"], datasets:[{{ data: opexEdgeData, backgroundColor: COLORS.edgePie }}] }},
    options:{{
      maintainAspectRatio: false,
      responsive: true,
      plugins:{{
        legend:{{position:"bottom", labels: {{font: {{size: 16}} }} }},
        display: false,
        tooltip:{{callbacks:{{label:(ctx)=> `${{CURRENCY.symbol}} ${{fmtMoneyShort(ctx.raw)}}`}} }}
      }}
    }}
  }});

  charts.capexPanelBar = new Chart(document.getElementById("capexPanelBar"), {{
    type: "bar",
    data: {{
      labels: [
        ["Panel", "(Device + Installation)"],
        ["Cables", "(Acquisition + Installation)"]
      ],
      datasets: [{{ data: capexPanelData, backgroundColor: COLORS.panelBars }}]
    }},
    options: {{
      maintainAspectRatio: false,
      scales: {{
        x: {{ ticks: {{ maxRotation: 0, minRotation: 0, font: {{size: 14}} }} }},
        y: {{ ticks: {{ callback: (v) => `${{CURRENCY.symbol}} ` + fmtMoneyLabel(v), font: {{size: 14}} }} }}
      }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: (ctx) => `${{CURRENCY.symbol}} ${{fmtMoneyLabel(ctx.raw)}}` }} }}
      }}
    }}
  }});

  charts.capexEdgeBar = new Chart(document.getElementById("capexEdgeBar"), {{
    type: "bar",
    data: {{
      labels: [
        ["Edge", "(Device + Installation)"],
        ["Fog", "(Device + Installation)"]
      ],
      datasets: [{{ data: capexEdgeData, backgroundColor: COLORS.edgeBars }}]
    }},
    options: {{
      maintainAspectRatio: false,
      scales: {{
        x: {{ ticks: {{ autoSkip: false, maxRotation: 0, minRotation: 0, font: {{size: 14}} }} }},
        y: {{ ticks: {{ callback: (v) => `${{CURRENCY.symbol}} ` + fmtMoneyLabel(v), font: {{size: 14}} }} }}
      }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: (ctx) => `${{CURRENCY.symbol}} ${{fmtMoneyLabel(ctx.raw)}}` }} }}
      }}
    }}
  }});
}}

// All dynamic configuration (including currency) is passed through render(model)
render({{
  currencySymbol: "{currency_symbol}",
  currencyLocale: "{currency_locale}",

  totalStreet: {len(df_panels) + len(df_edges)},
  edgeCount: {len(df_edges)},
  panelCount: {len(df_panels)},

  opexPanelMaint: {panel_report_data.at["Annual Maintenance Price", "Values"]},
  opexPanelEnergy: {panel_report_data.at["Annual Energy Price", "Values"]},

  opexEdgeEnergy: {Edge_fog_report_data.at["Annual Edge Energy Price", "Values"]},
  opexEdgeMaint: {Edge_fog_report_data.at["Annual Edges Maintenance Price", "Values"]},
  opexFogEnergy: {Edge_fog_report_data.at["Annual Fog Energy Price", "Values"]},
  opexFogMaint: {Edge_fog_report_data.at["Annual Fogs Maintenance Price", "Values"]},

  capexPanelDevice: {panel_report_data.at["Total Panel Price", "Values"] + panel_report_data.at["Total Installation Price", "Values"]},
  capexCables: {panel_report_data.at["Total Cable Price", "Values"] + panel_report_data.at["Total Cable Installation Price", "Values"]},

  capexEdgeDevice: {Edge_fog_report_data.at["Total Edges Price", "Values"] + Edge_fog_report_data.at["Total Edges Installation Price", "Values"]},
  capexFogDevice: {Edge_fog_report_data.at["Total Fogs Price", "Values"] + Edge_fog_report_data.at["Total Fogs Installation Price", "Values"]}
}});
</script>
</body>
</html>
"""

    path = f"{file_path}/devices_dashboard_costs.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_code)
    print(f"General dashboard saved to {path}.\n")