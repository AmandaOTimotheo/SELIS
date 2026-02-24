"""Web-based parameter editor and process runner for Generator_Math."""

import json
import os
import signal
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template_string, request
from pydantic import ValidationError
from waitress import serve

from parameters_model_v2 import ParametersV2


TOP_LEVEL_ORDER = [
    "debug",
    "path_json",
    "collision",
    "clustering",
    "simulation",
    "financial",
]

HELP_TEXT = {
    "debug": "Enables debug mode. When true, publisher waits for debugger on port 5678.",
    "path_json": "Directory where the effective JSON used in the run is saved with timestamp (used_parameters_YYYYMMDD_HHMMSS.json).",
    "collision.enable": "Enables the message collision analysis module.",
    "collision.save_data_path": "Folder where the collision report is saved (collision_report.csv).",
    "collision.num_edges": "Number of transmitting edges considered in collision simulation.",
    "collision.msg_transmission_time": "Transmission duration (s) of one message.",
    "collision.t_simulation_cycles": "Number of collision simulation cycles (higher = more stable result).",
    "collision.transmission_interval_edge": "Base interval (s) between transmissions for each edge.",
    "collision.num_channels": "Number of channels available for simultaneous transmission.",
    "collision.poisson_calculation_enable": "Enables statistical calculation using a Poisson process.",
    "collision.monte_carlo_simulation_enable": "Enables Monte Carlo collision simulation.",
    "clustering.raw_database.path": "Path to raw CSV containing lighting points.",
    "clustering.raw_database.fields.id": "CSV column name representing the point ID.",
    "clustering.raw_database.fields.lat": "CSV column name for latitude.",
    "clustering.raw_database.fields.lon": "CSV column name for longitude.",
    "clustering.raw_database.fields.rated_power": "CSV column name for rated power.",
    "clustering.raw_database.fields.rated_voltage": "CSV column name for rated voltage.",
    "clustering.raw_database.fields.rated_power_factor": "CSV column name for rated power factor.",
    "clustering.final_path": "Output folder for clustering artifacts (CSV + maps).",
    "clustering.interactive_map_path": "Optional path for an additional interactive map.",
    "clustering.clustering": "Runs the clustering stage to generate device data.",
    "clustering.generate_density_map": "Generates a density map from raw data.",
    "clustering.generate_clustered_map": "Generates a map of resulting groups (panel/edge/fog).",
    "clustering.devices.panel.priority": "Point allocation priority for panel (higher value runs first).",
    "clustering.devices.panel.percentage": "Share of total points allocated to panel (0 to 1).",
    "clustering.devices.panel.n_branchs": "Number of branches per panel.",
    "clustering.devices.panel.min_points_branch": "Minimum number of points per branch.",
    "clustering.devices.panel.max_points_branch": "Maximum number of points per branch.",
    "clustering.devices.edge_fog.priority": "Allocation priority for edge/fog.",
    "clustering.devices.edge_fog.percentage": "Share of total points allocated to edge/fog (0 to 1).",
    "clustering.devices.edge_fog.max_range_km": "Maximum distance (km) for grouping around each fog.",
    "clustering.devices.edge_fog.max_points": "Maximum number of points served by one fog.",
    "simulation.window.use_current_time_and_date": "If true, uses current date/time at start; if false, uses the manual window below.",
    "simulation.window.simulation_start_date": "Manual simulation start date (MM/DD/YYYY).",
    "simulation.window.simulation_start_time": "Manual simulation start time (HH:MM).",
    "simulation.window.time_zone": "Time zone used for schedule and publication logic (e.g., America/Sao_Paulo).",
    "simulation.window.simulation_stop_date": "Manual simulation end date (MM/DD/YYYY).",
    "simulation.window.simulation_stop_time": "Manual simulation end time (HH:MM).",
    "simulation.persistence.save_simulation_data": "Defines whether simulated data should be persisted to files.",
    "simulation.persistence.csv_lines_limit": "Maximum lines per CSV file before creating a new part.",
    "simulation.generation.voltage.v_upper_variation": "Upper variation applied to synthetic voltage generation.",
    "simulation.generation.voltage.v_lower_variation": "Lower variation applied to synthetic voltage generation.",
    "simulation.generation.current.c_upper_variation": "Upper variation applied to synthetic current generation.",
    "simulation.generation.current.c_lower_variation": "Lower variation applied to synthetic current generation.",
    "simulation.generation.consumption.power_factor_variation": "Power factor variation used in synthetic generation.",
    "simulation.daylight.sunrise_start": "Start of sunrise interval (affects day/night logic and current).",
    "simulation.daylight.sunrise_end": "End of sunrise interval.",
    "simulation.daylight.sunset_start": "Start of sunset interval.",
    "simulation.daylight.sunset_end": "End of sunset interval.",
    "simulation.devices.panel.modes.offline_simulation.enable": "Enables offline simulation for panel. Cannot be true together with real_time_simulation.enable.",
    "simulation.devices.panel.modes.offline_simulation.save_data_path": "Folder to save panel offline simulation data.",
    "simulation.devices.panel.modes.real_time_simulation.enable": "Enables real-time publication for panel. Cannot be true together with offline_simulation.enable.",
    "simulation.devices.panel.modes.real_time_simulation.is_print_publish": "If true, prints each published real-time payload in logs (panel).",
    "simulation.devices.panel.modes.real_time_simulation.mqtt.broker_address": "MQTT broker address for panel publication.",
    "simulation.devices.panel.modes.real_time_simulation.mqtt.broker_port": "MQTT broker port for panel publication.",
    "simulation.devices.panel.modes.real_time_simulation.topics": "MQTT publication topic for panel.",
    "simulation.devices.panel.publication_interval_day": "Interval (s) between publications during daytime (panel).",
    "simulation.devices.panel.publication_interval_night": "Interval (s) between publications during nighttime (panel).",
    "simulation.devices.edge_fog.modes.offline_simulation.enable": "Enables offline simulation for edge/fog. Cannot be true together with real_time_simulation.enable.",
    "simulation.devices.edge_fog.modes.offline_simulation.save_data_path": "Folder to save edge/fog offline simulation data.",
    "simulation.devices.edge_fog.modes.real_time_simulation.enable": "Enables real-time publication for edge/fog. Cannot be true together with offline_simulation.enable.",
    "simulation.devices.edge_fog.modes.real_time_simulation.is_print_publish": "If true, prints each published real-time payload in logs (edge/fog).",
    "simulation.devices.edge_fog.modes.real_time_simulation.mqtt.broker_address": "MQTT broker address for edge/fog publication.",
    "simulation.devices.edge_fog.modes.real_time_simulation.mqtt.broker_port": "MQTT broker port for edge/fog publication.",
    "simulation.devices.edge_fog.modes.real_time_simulation.topics": "MQTT publication topic for edge/fog.",
    "simulation.devices.edge_fog.publication_interval_day": "Interval (s) between publications during daytime (edge/fog).",
    "simulation.devices.edge_fog.publication_interval_night": "Interval (s) between publications during nighttime (edge/fog).",
    "simulation.devices.panel.failure_rate.day_on": "Failure probability during daytime (day_on mask).",
    "simulation.devices.panel.failure_rate.night_low_voltage": "Probability of low voltage at night.",
    "simulation.devices.panel.failure_rate.night_zero_voltage": "Probability of zero voltage at night (off).",
    "simulation.devices.panel.failure_rate.transmission": "Message transmission failure probability.",
    "simulation.devices.edge_fog.failure_rate.day_on": "Failure probability during daytime (edge/fog).",
    "simulation.devices.edge_fog.failure_rate.night_low_voltage": "Probability of low voltage at night (edge/fog).",
    "simulation.devices.edge_fog.failure_rate.night_zero_voltage": "Probability of zero voltage at night (edge/fog).",
    "simulation.devices.edge_fog.failure_rate.transmission": "Message transmission failure probability (edge/fog).",
    "simulation.devices.panel.database.path": "Input CSV for panel simulation (generated by clustering or existing file).",
    "simulation.devices.edge_fog.database.path": "Input CSV for edge/fog simulation (generated by clustering or existing file).",
    "financial.general.used_currency": "Base currency used in calculations and reports (e.g., USD, BRL).",
    "financial.general.conversion_to_other_currency.enable": "If true, converts prices from base currency to the target currency below.",
    "financial.general.conversion_to_other_currency.To": "Target currency for conversion (must exist in currency_to_USD).",
    "financial.general.price_kWh": "Energy price per kWh.",
    "financial.general.save_report_path": "Output folder for financial reports (CSV, XLSX, PNG, HTML).",
    "financial.general.estimated_vs_simulated.enable": "Enables comparison between estimated consumption (contract) and simulated consumption.",
    "financial.general.estimated_vs_simulated.yellow_flag_add_price": "Yellow-flag surcharge per 100 kWh.",
    "financial.general.estimated_vs_simulated.red_flag_1_add_price": "Red-flag level 1 surcharge per 100 kWh.",
    "financial.general.estimated_vs_simulated.red_flag_2_add_price": "Red-flag level 2 surcharge per 100 kWh.",
    "financial.general.estimated_vs_simulated.estimated_hours_on_per_day": "Average daily on-hours used in estimated calculation.",
    "financial.devices.panel.communication_cost_report.enable_consumption_report": "Generates simulated energy consumption report for panel.",
    "financial.devices.panel.communication_cost_report.enable_transmission_and_storage": "Calculates transmission and storage costs for panel.",
    "financial.devices.panel.communication_cost_report.enable_capex": "Includes CAPEX report for panel.",
    "financial.devices.panel.communication_cost_report.enable_opex": "Includes OPEX report for panel.",
    "financial.devices.edge_fog.communication_cost_report.enable_consumption_report": "Generates simulated energy consumption report for edge/fog.",
    "financial.devices.edge_fog.communication_cost_report.enable_transmission_and_storage": "Calculates transmission and storage costs for edge/fog.",
    "financial.devices.edge_fog.communication_cost_report.enable_capex": "Includes CAPEX report for edge/fog.",
    "financial.devices.edge_fog.communication_cost_report.enable_opex": "Includes OPEX report for edge/fog.",
    "financial.devices.panel.communication_cost_report.storage.storage_cost_per_GB": "Storage cost per GB.",
    "financial.devices.panel.communication_cost_report.storage.months_of_storage": "Storage horizon in months used in cost calculation.",
    "financial.devices.edge_fog.communication_cost_report.storage.storage_cost_per_GB": "Storage cost per GB.",
    "financial.devices.edge_fog.communication_cost_report.storage.months_of_storage": "Storage horizon in months used in cost calculation.",
    "financial.devices.panel.communication_cost_report.transmission.connectivity_cost_per_minute": "Base connectivity cost per minute.",
    "financial.devices.panel.communication_cost_report.transmission.cost_per_mqtt_msg": "Unit cost per MQTT message.",
    "financial.devices.panel.communication_cost_report.transmission.max_KBs_per_message": "Maximum message size (KB) used to compute billed message count.",
    "financial.devices.edge_fog.communication_cost_report.transmission.connectivity_cost_per_minute": "Base connectivity cost per minute.",
    "financial.devices.edge_fog.communication_cost_report.transmission.cost_per_mqtt_msg": "Unit cost per MQTT message.",
    "financial.devices.edge_fog.communication_cost_report.transmission.max_KBs_per_message": "Maximum message size (KB) used to compute billed message count.",
    "financial.devices.panel.communication_cost_report.chosen_communication": "Active technology/input under communication_type for panel.",
    "financial.devices.edge_fog.communication_cost_report.chosen_communication": "Active technology/input under communication_type for edge/fog.",
}

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Generator Math - Parameters Web UI</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --card: #ffffff;
      --ink: #1f2937;
      --muted: #6b7280;
      --accent: #1d4ed8;
      --border: #dbe2ee;
      --warn: #b45309;
      --error: #b91c1c;
      --ok: #15803d;
      --code: #111827;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
      min-height: 100vh;
    }
    .wrap {
      max-width: 1400px;
      margin: 0 auto;
      padding: 16px;
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 16px;
      min-height: calc(100vh - 32px);
      align-items: stretch;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      min-height: 0;
    }
    .title {
      margin: 0 0 12px 0;
      font-size: 22px;
      font-weight: 700;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
    }
    button {
      border: 1px solid var(--border);
      background: #fff;
      color: var(--ink);
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 600;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    button.warn {
      background: #fef3c7;
      color: #92400e;
      border-color: #fcd34d;
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.6;
    }
    .status {
      margin: 6px 0 0 0;
      color: var(--muted);
      font-size: 13px;
    }
    .section {
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-bottom: 8px;
      background: #fdfefe;
    }
    .section > summary {
      cursor: pointer;
      padding: 8px 10px;
      font-weight: 700;
      list-style: none;
      border-bottom: 1px solid #eef2f8;
    }
    .section > summary::-webkit-details-marker {
      display: none;
    }
    .section-body {
      padding: 8px;
    }
    .field-row {
      display: grid;
      grid-template-columns: 320px 26px 1fr;
      align-items: center;
      gap: 8px;
      padding: 4px 0;
    }
    .field-label {
      font-weight: 600;
      color: #1f2a3b;
      word-break: break-word;
    }
    .info {
      width: 20px;
      height: 20px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #93c5fd;
      color: #1d4ed8;
      border-radius: 50%;
      font-size: 11px;
      cursor: help;
      user-select: none;
    }
    input[type="text"], input[type="number"] {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 6px 8px;
    }
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
    }
    .field-editor {
      display: flex;
      align-items: center;
      gap: 6px;
      width: 100%;
    }
    .picker-btn {
      padding: 6px 8px;
      border-radius: 7px;
      border: 1px solid #bcd0ef;
      background: #f2f7ff;
      color: #1d4e89;
      font-size: 12px;
      white-space: nowrap;
    }
    .picker-btn:hover {
      background: #e8f0ff;
      border-color: #94b2e8;
    }
    .mono {
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      background: #0b1020;
      color: #d1e0ff;
      border-radius: 8px;
      border: 1px solid #27324a;
      padding: 10px;
      height: 100%;
      min-height: 0;
      max-height: 100%;
      overflow-y: auto;
      overflow-x: auto;
      white-space: pre-wrap;
      margin: 0;
    }
    .mono .log-link {
      color: #8ec9ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    .mono .log-link:hover {
      color: #c7e5ff;
    }
    .kpi-link {
      color: #1d4ed8;
      text-decoration: underline;
      text-underline-offset: 2px;
      word-break: break-all;
    }
    .terminal-panel {
      display: flex;
      flex-direction: column;
      align-self: start;
      position: sticky;
      top: 16px;
      height: calc(100vh - 32px);
      max-height: calc(100vh - 32px);
      min-height: 0;
    }
    .terminal-panel .mono {
      flex: 1 1 auto;
      min-height: 0;
    }
    .errors {
      margin-top: 8px;
      color: var(--error);
      font-size: 13px;
      white-space: pre-wrap;
      min-height: 24px;
    }
    .kpi {
      display: grid;
      gap: 8px;
      margin-bottom: 10px;
      font-size: 13px;
    }
    .kpi-line b { color: var(--ink); }
    .ok { color: var(--ok); }
    .warn-txt { color: var(--warn); }
    .muted { color: var(--muted); }
    @media (max-width: 1100px) {
      .wrap {
        grid-template-columns: 1fr;
      }
      .terminal-panel {
        position: static;
        top: auto;
        height: auto;
        max-height: none;
      }
      .terminal-panel .mono {
        max-height: 60vh;
      }
      .field-row {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <h1 class="title">Generator Math - Parameters</h1>
      <div class="toolbar">
        <button id="btn-import">Import JSON</button>
        <input id="import-input" type="file" accept=".json,application/json" style="display:none" />
        <button id="btn-default">Reload Default</button>
        <button id="btn-validate">Validate</button>
        <button id="btn-download">Download JSON</button>
        <button id="btn-run" class="primary">Run Program</button>
        <button id="btn-stop" class="warn">Stop</button>
      </div>
      <p class="status" id="ui-status">Ready.</p>
      <div class="errors" id="validation-errors"></div>
      <div id="form-root"></div>
    </section>

    <aside class="card terminal-panel">
      <h2 class="title" style="font-size:18px">Execution</h2>
      <div class="kpi">
        <div class="kpi-line"><b>Running:</b> <span id="run-running" class="muted">no</span></div>
        <div class="kpi-line"><b>Exit code:</b> <span id="run-exit" class="muted">-</span></div>
        <div class="kpi-line"><b>Started at:</b> <span id="run-started" class="muted">-</span></div>
        <div class="kpi-line"><b>Finished at:</b> <span id="run-finished" class="muted">-</span></div>
        <div class="kpi-line"><b>Params file:</b> <span id="run-params" class="muted">-</span></div>
      </div>
      <pre id="log-output" class="mono"></pre>
    </aside>
  </div>

  <script>
    const TOP_ORDER = {{ top_order | tojson }};
    const HELP_TEXT = {{ help_text | tojson }};
    const INITIAL_STATE = {{ initial_state | tojson }};
    const PATH_PICKER_AVAILABLE = {{ path_picker_available | tojson }};
    const PATH_PICKER_MESSAGE = {{ path_picker_message | tojson }};

    let state = deepClone(INITIAL_STATE);
    let logsCursor = 0;
    let sectionState = new Map();
    let preservedScrollY = 0;
    const SPECIAL_PATH_MARKERS = [
      "saved to ",
      "saved at ",
      "using parameters file: ",
      "--params ",
    ];
    const TRAILING_PATH_PUNCTUATION = ").,;:!?";

    function deepClone(obj) {
      return JSON.parse(JSON.stringify(obj));
    }

    function isObject(value) {
      return value !== null && typeof value === "object" && !Array.isArray(value);
    }

    function getByPath(root, path) {
      let cur = root;
      for (const key of path) {
        if (!isObject(cur) || !(key in cur)) {
          return undefined;
        }
        cur = cur[key];
      }
      return cur;
    }

    function setByPath(root, path, value) {
      let cur = root;
      for (let i = 0; i < path.length - 1; i += 1) {
        const key = path[i];
        if (!isObject(cur[key])) {
          cur[key] = {};
        }
        cur = cur[key];
      }
      cur[path[path.length - 1]] = value;
    }

    function captureViewState() {
      const root = document.getElementById("form-root");
      if (!root) return;
      sectionState = new Map();
      Array.from(root.querySelectorAll("details.section"))
        .filter((el) => el.dataset.sectionPath)
        .forEach((el) => {
          sectionState.set(el.dataset.sectionPath, Boolean(el.open));
        });
      preservedScrollY = window.scrollY || document.documentElement.scrollTop || 0;
    }

    function restoreViewState() {
      window.requestAnimationFrame(() => {
        window.scrollTo(0, preservedScrollY);
      });
    }

    function boolAt(path, fallback = false) {
      const value = getByPath(state, path.split("."));
      if (typeof value === "boolean") {
        return value;
      }
      return fallback;
    }

    function shouldRenderPath(pathArray) {
      const path = pathArray.join(".");

      if (path !== "collision.enable" && path.startsWith("collision.") && !boolAt("collision.enable", false)) {
        return false;
      }

      const clusteringActive =
        boolAt("clustering.clustering", false) ||
        boolAt("clustering.generate_density_map", false) ||
        boolAt("clustering.generate_clustered_map", false);

      if (
        (path === "clustering.raw_database" ||
         path.startsWith("clustering.raw_database.") ||
         path === "clustering.final_path" ||
         path === "clustering.devices" ||
         path.startsWith("clustering.devices.")) &&
        !clusteringActive
      ) {
        return false;
      }

      if (path.endsWith(".offline_simulation.save_data_path")) {
        const enablePath = path.replace(".save_data_path", ".enable");
        return boolAt(enablePath, false);
      }

      if (path.includes(".real_time_simulation.") && !path.endsWith(".real_time_simulation.enable")) {
        const base = path.split(".real_time_simulation.")[0];
        return boolAt(base + ".real_time_simulation.enable", false);
      }

      return true;
    }

    function pairedSimulationPath(path) {
      if (path.endsWith(".offline_simulation.enable")) {
        return path.replace(".offline_simulation.enable", ".real_time_simulation.enable");
      }
      if (path.endsWith(".real_time_simulation.enable")) {
        return path.replace(".real_time_simulation.enable", ".offline_simulation.enable");
      }
      return null;
    }

    function inferType(value) {
      if (typeof value === "boolean") return "bool";
      if (typeof value === "number") return Number.isInteger(value) ? "int" : "float";
      return "string";
    }

    function helpText(path) {
      if (HELP_TEXT[path]) {
        return HELP_TEXT[path];
      }
      if (path.includes(".database.fields.")) {
        return "Exact CSV column name mapped to this internal simulation attribute.";
      }
      if (path.includes(".raw_database.labels.") || path.includes(".devices.panel.labels.") || path.includes(".devices.edge_fog.labels.")) {
        return "Field shown in map/visualization popups for easier point inspection.";
      }
      if (path.includes(".publication_interval_day")) {
        return "Interval, in seconds, between publications during daytime.";
      }
      if (path.includes(".publication_interval_night")) {
        return "Interval, in seconds, between publications during nighttime.";
      }
      if (path.includes(".failure_rate.day_on")) {
        return "Failure probability in daytime mode used by synthetic generation.";
      }
      if (path.includes(".failure_rate.night_low_voltage")) {
        return "Probability of low-voltage event at night.";
      }
      if (path.includes(".failure_rate.night_zero_voltage")) {
        return "Probability of zero-voltage event at night (off).";
      }
      if (path.includes(".failure_rate.transmission")) {
        return "Message transmission failure probability.";
      }
      if (path.includes(".modes.offline_simulation.enable")) {
        return "Enables offline mode. Cannot be true together with the same device real-time mode.";
      }
      if (path.includes(".modes.real_time_simulation.enable")) {
        return "Enables real-time mode. Cannot be true together with the same device offline mode.";
      }
      if (path.includes(".modes.real_time_simulation.topics")) {
        return "MQTT topic used to publish device messages.";
      }
      if (path.includes(".modes.real_time_simulation.mqtt.broker_address")) {
        return "MQTT broker address.";
      }
      if (path.includes(".modes.real_time_simulation.mqtt.broker_port")) {
        return "MQTT broker port.";
      }
      if (path.includes(".modes.real_time_simulation.is_print_publish")) {
        return "If enabled, prints every MQTT published payload in logs.";
      }
      if (path.includes(".transmission.internet_cost_MB_BRL.")) {
        return "Internet plan price for the MB limit defined by this key.";
      }
      if (path.includes(".communication_type.") && path.endsWith(".overhead_bytes")) {
        return "Protocol overhead per message (bytes) used in transmission cost calculations.";
      }
      if (path.includes(".communication_type.") && path.includes(".price_")) {
        return "Unit price used in CAPEX/OPEX calculation for the selected technology.";
      }
      if (path.includes(".communication_type.") && path.endsWith("_power_W")) {
        return "Electrical power in watts used to calculate annual energy cost.";
      }
      if (path.includes(".payloads.send.transmission_format")) {
        return "Transmission payload format (JSON or CBOR).";
      }
      if (path.includes(".payloads.save.storage_format")) {
        return "Simulation storage format (SQL or CSV).";
      }
      if (path.includes(".payloads.header.")) {
        return "Final field name in the generated/published payload.";
      }
      if (path.includes(".payloads.n_decimals.measures.")) {
        return "Number of decimal places applied to this measurement field in the payload.";
      }
      if (path.includes(".payloads.send.general.") || path.includes(".payloads.send.measures.")) {
        return "Defines whether this field is included in the send payload.";
      }
      if (path.includes(".payloads.save.general.") || path.includes(".payloads.save.measures.")) {
        return "Defines whether this field is included in the stored payload.";
      }
      if (path.includes(".conversion_to_other_currency.To")) {
        return "Target currency for automatic cost conversion.";
      }
      if (path.includes(".currency_to_USD.")) {
        return "Currency quotation to USD used in conversion.";
      }
      if (path.endsWith("_date")) {
        return "Date format: MM/DD/YYYY";
      }
      if (path.endsWith("_time")) {
        return "Time format: HH:MM";
      }
      if (path.endsWith("path") || path.endsWith("_path")) {
        return "Filesystem path.";
      }
      if (path.endsWith(".enable")) {
        return "Enable or disable this block.";
      }
      return "Field: " + path;
    }

    function parseInputValue(raw, kind) {
      if (kind === "int") {
        if (raw.trim() === "") return "";
        const parsed = Number.parseInt(raw, 10);
        return Number.isNaN(parsed) ? raw : parsed;
      }
      if (kind === "float") {
        if (raw.trim() === "") return "";
        const normalized = raw.replace(",", ".");
        const parsed = Number.parseFloat(normalized);
        return Number.isNaN(parsed) ? raw : parsed;
      }
      return raw;
    }

    function isPathField(path) {
      return path === "path_json" || path.endsWith(".path") || path.endsWith("_path");
    }

    function hasFileExtension(value) {
      if (typeof value !== "string") {
        return false;
      }
      const trimmed = value.trim();
      if (!trimmed) {
        return false;
      }
      const normalized = trimmed.split("\\\\").join("/");
      const name = normalized.split("/").pop() || "";
      if (!name || name === "." || name === "..") {
        return false;
      }
      const dotPos = name.lastIndexOf(".");
      return dotPos > 0 && dotPos < name.length - 1;
    }

    function pickerModeForValue(value) {
      return hasFileExtension(value) ? "file" : "dir";
    }

    async function pickPathFromServer(mode, currentValue) {
      const response = await fetch("/api/pick-path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: mode, current: currentValue || "" }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.message || "Could not open path picker.");
      }
      return payload;
    }

    function sectionPalette(depth) {
      const d = Math.min(Math.max(depth, 0), 6);
      const hue = 212;
      const saturation = 44;
      return {
        bg: `hsl(${hue} ${saturation}% ${84 + d * 2.3}%)`,
        border: `hsl(${hue} ${saturation - 8}% ${60 + d * 4.0}%)`,
        header: `hsl(${hue} ${saturation + 6}% ${78 + d * 2.9}%)`,
        accent: `hsl(${hue} ${saturation + 10}% ${36 + d * 5.3}%)`,
      };
    }

    function createFieldRow(key, value, pathArray) {
      const path = pathArray.join(".");
      const row = document.createElement("div");
      row.className = "field-row";

      const label = document.createElement("div");
      label.className = "field-label";
      label.textContent = key;
      row.appendChild(label);

      const info = document.createElement("span");
      info.className = "info";
      info.textContent = "i";
      info.title = helpText(path);
      row.appendChild(info);

      const kind = inferType(value);
      if (kind === "bool") {
        const input = document.createElement("input");
        input.type = "checkbox";
        input.dataset.inputPath = path;
        input.checked = Boolean(value);
        input.addEventListener("change", () => {
          let nextValue = input.checked;
          const pairPath = pairedSimulationPath(path);
          if (pairPath && nextValue) {
            const pairValue = getByPath(state, pairPath.split("."));
            if (pairValue === true) {
              alert("offline_simulation.enable and real_time_simulation.enable cannot both be true.");
              nextValue = false;
              input.checked = false;
            }
          }
          setByPath(state, pathArray, nextValue);
          renderForm();
        });
        row.appendChild(input);
      } else {
        const editor = document.createElement("div");
        editor.className = "field-editor";

        const input = document.createElement("input");
        input.type = kind === "string" ? "text" : "number";
        input.step = kind === "int" ? "1" : "any";
        input.dataset.inputPath = path;
        input.value = value === null ? "" : String(value);
        input.addEventListener("change", () => {
          const parsed = parseInputValue(input.value, kind);
          setByPath(state, pathArray, parsed);
        });
        editor.appendChild(input);

        if (isPathField(path)) {
          const pickerBtn = document.createElement("button");
          pickerBtn.type = "button";
          pickerBtn.className = "picker-btn";

          function refreshPickerButton() {
            if (!PATH_PICKER_AVAILABLE) {
              pickerBtn.dataset.mode = "manual";
              pickerBtn.textContent = "Manual";
              pickerBtn.title = PATH_PICKER_MESSAGE || "Path picker unavailable. Type path manually.";
              pickerBtn.disabled = true;
              return;
            }
            const mode = pickerModeForValue(input.value);
            pickerBtn.dataset.mode = mode;
            pickerBtn.textContent = mode === "file" ? "File..." : "Folder...";
            pickerBtn.title = mode === "file"
              ? "Select file from system"
              : "Select folder from system";
            pickerBtn.disabled = false;
          }

          refreshPickerButton();
          input.addEventListener("input", refreshPickerButton);

          pickerBtn.addEventListener("click", async () => {
            if (!PATH_PICKER_AVAILABLE) {
              setStatus(PATH_PICKER_MESSAGE || "Path picker unavailable. Type path manually.", "warn-txt");
              return;
            }
            const mode = pickerBtn.dataset.mode || pickerModeForValue(input.value);
            try {
              const payload = await pickPathFromServer(mode, input.value);
              if (payload.cancelled) {
                return;
              }
              input.value = payload.path || "";
              setByPath(state, pathArray, input.value);
              refreshPickerButton();
              setValidationErrors("");
              setStatus("Path selected.", "ok");
            } catch (err) {
              const msg = err instanceof Error ? err.message : String(err);
              setStatus(msg || "Failed to open path picker.", "warn-txt");
              setValidationErrors(msg || "Path picker request failed.");
            }
          });

          editor.appendChild(pickerBtn);
        }

        row.appendChild(editor);
      }

      return row;
    }

    function createSection(key, value, pathArray, depth) {
      const path = pathArray.join(".");
      const details = document.createElement("details");
      details.className = "section";
      details.dataset.sectionPath = path;
      details.open = sectionState.has(path) ? Boolean(sectionState.get(path)) : depth <= 0;
      const palette = sectionPalette(depth);
      details.style.background = palette.bg;
      details.style.borderColor = palette.border;
      details.style.borderLeft = `4px solid ${palette.accent}`;
      details.addEventListener("toggle", () => {
        sectionState.set(path, Boolean(details.open));
      });

      const summary = document.createElement("summary");
      summary.textContent = key;
      summary.title = helpText(path);
      summary.style.background = palette.header;
      summary.style.borderBottomColor = palette.border;
      details.appendChild(summary);

      const body = document.createElement("div");
      body.className = "section-body";

      const entries = Object.entries(value);
      const ordered = [];
      for (const item of entries) {
        if (!isObject(item[1])) {
          ordered.push(item);
        }
      }
      for (const item of entries) {
        if (isObject(item[1])) {
          ordered.push(item);
        }
      }

      for (const [childKey, childValue] of ordered) {
        const childPath = [...pathArray, childKey];
        if (!shouldRenderPath(childPath)) {
          continue;
        }
        if (isObject(childValue)) {
          body.appendChild(createSection(childKey, childValue, childPath, depth + 1));
        } else {
          body.appendChild(createFieldRow(childKey, childValue, childPath));
        }
      }

      details.appendChild(body);
      return details;
    }

    function renderForm() {
      captureViewState();
      const root = document.getElementById("form-root");
      root.innerHTML = "";

      const keys = [];
      for (const key of TOP_ORDER) {
        if (Object.prototype.hasOwnProperty.call(state, key)) {
          keys.push(key);
        }
      }
      for (const key of Object.keys(state)) {
        if (!keys.includes(key)) {
          keys.push(key);
        }
      }

      for (const key of keys) {
        const value = state[key];
        if (isObject(value)) {
          root.appendChild(createSection(key, value, [key], 0));
        } else {
          root.appendChild(createFieldRow(key, value, [key]));
        }
      }
      restoreViewState();
    }

    function setStatus(text, cssClass = "muted") {
      const el = document.getElementById("ui-status");
      el.textContent = text;
      el.className = "status " + cssClass;
    }

    function setValidationErrors(text) {
      document.getElementById("validation-errors").textContent = text || "";
    }

    function splitTrailingPathPunctuation(text) {
      let end = text.length;
      while (end > 0 && TRAILING_PATH_PUNCTUATION.includes(text[end - 1])) {
        end -= 1;
      }
      return {
        value: text.slice(0, end),
        trailing: text.slice(end),
      };
    }

    function isHttpUrl(value) {
      return value.startsWith("http://") || value.startsWith("https://");
    }

    function isWindowsDrivePath(value) {
      if (!value || value.length < 3) {
        return false;
      }
      const c = value.charCodeAt(0);
      const isLetter = (c >= 65 && c <= 90) || (c >= 97 && c <= 122);
      return isLetter && value[1] === ":" && (value[2] === "\\\\" || value[2] === "/");
    }

    function isUncPath(value) {
      return typeof value === "string" && value.startsWith("\\\\\\\\");
    }

    function isPosixAbsolutePath(value) {
      return value.startsWith("/");
    }

    function toFileHref(pathValue) {
      if (isWindowsDrivePath(pathValue)) {
        return "file:///" + encodeURI(pathValue.replace(/\\\\/g, "/"));
      }
      if (isUncPath(pathValue)) {
        const normalized = pathValue.replace(/^\\\\\\\\/, "").replace(/\\\\/g, "/");
        return "file://" + encodeURI(normalized);
      }
      if (isPosixAbsolutePath(pathValue)) {
        return "file://" + encodeURI(pathValue);
      }
      return "";
    }

    function createAnchorNode(href, label, cssClass) {
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.className = cssClass;
      anchor.textContent = label;
      return anchor;
    }

    function createPathOrUrlLink(value, cssClass = "log-link") {
      if (!value) {
        return null;
      }
      if (isHttpUrl(value)) {
        return createAnchorNode(value, value, cssClass);
      }
      const href = toFileHref(value);
      if (!href) {
        return null;
      }
      return createAnchorNode(href, value, cssClass);
    }

    function findNextUrl(text, fromIndex) {
      const httpIndex = text.indexOf("http://", fromIndex);
      const httpsIndex = text.indexOf("https://", fromIndex);

      if (httpIndex < 0 && httpsIndex < 0) {
        return null;
      }

      let start = -1;
      if (httpIndex < 0) {
        start = httpsIndex;
      } else if (httpsIndex < 0) {
        start = httpIndex;
      } else {
        start = Math.min(httpIndex, httpsIndex);
      }

      let end = start;
      while (end < text.length) {
        const ch = text[end];
        if (ch === " " || ch === "\\t" || ch === "\\n" || ch === "<" || ch === ">" || ch === '"' || ch === "'") {
          break;
        }
        end += 1;
      }

      return { start, end, value: text.slice(start, end) };
    }

    function appendUrls(container, text) {
      let cursor = 0;
      let found = findNextUrl(text, cursor);
      while (found) {
        const value = found.value;
        const start = found.start;
        if (start > cursor) {
          container.appendChild(document.createTextNode(text.slice(cursor, start)));
        }
        const link = createPathOrUrlLink(value);
        if (link) {
          container.appendChild(link);
        } else {
          container.appendChild(document.createTextNode(value));
        }
        cursor = found.end;
        found = findNextUrl(text, cursor);
      }

      if (cursor < text.length) {
        container.appendChild(document.createTextNode(text.slice(cursor)));
      }
    }

    function findSpecialPathMarker(line) {
      const lowered = line.toLowerCase();
      let chosen = null;
      for (const marker of SPECIAL_PATH_MARKERS) {
        const index = lowered.indexOf(marker);
        if (index < 0) {
          continue;
        }
        if (!chosen || index < chosen.index) {
          chosen = { index, marker };
        }
      }
      return chosen;
    }

    function appendSpecialPathLine(container, line) {
      const markerInfo = findSpecialPathMarker(line);
      if (!markerInfo) {
        return false;
      }

      const markerStart = markerInfo.index;
      const markerEnd = markerStart + markerInfo.marker.length;
      const prefix = line.slice(0, markerStart);
      const markerOriginalCase = line.slice(markerStart, markerEnd);
      const rawPath = line.slice(markerEnd).trim();

      if (prefix) {
        container.appendChild(document.createTextNode(prefix));
      }
      container.appendChild(document.createTextNode(markerOriginalCase));

      if (!rawPath) {
        return true;
      }

      const trimmed = splitTrailingPathPunctuation(rawPath);
      const link = createPathOrUrlLink(trimmed.value);
      if (link) {
        container.appendChild(link);
      } else {
        container.appendChild(document.createTextNode(trimmed.value));
      }
      if (trimmed.trailing) {
        container.appendChild(document.createTextNode(trimmed.trailing));
      }
      return true;
    }

    function setPathValue(elementId, value) {
      const target = document.getElementById(elementId);
      if (target.replaceChildren) {
        target.replaceChildren();
      } else {
        target.innerHTML = "";
      }
      if (!value) {
        target.textContent = "-";
        return;
      }
      const link = createPathOrUrlLink(value, "kpi-link");
      if (link) {
        target.appendChild(link);
      } else {
        target.textContent = value;
      }
    }

    const MAX_LOG_LINES = 2000;
    let logLines = [];

    function renderLogLines() {
      const pre = document.getElementById("log-output");
      if (pre.replaceChildren) {
        pre.replaceChildren();
      } else {
        pre.innerHTML = "";
      }
      for (const line of logLines) {
        const linked = appendSpecialPathLine(pre, line);
        if (!linked) {
          appendUrls(pre, line);
        }
        pre.appendChild(document.createTextNode("\\n"));
      }
      pre.scrollTop = pre.scrollHeight;
    }

    function appendLogs(lines) {
      if (!lines || lines.length === 0) {
        return;
      }
      logLines = logLines.concat(lines.map((line) => String(line)));
      if (logLines.length > MAX_LOG_LINES) {
        logLines = logLines.slice(logLines.length - MAX_LOG_LINES);
      }
      renderLogLines();
    }

    async function loadDefaultFromServer() {
      const response = await fetch("/api/default");
      const data = await response.json();
      state = deepClone(data.params);
      renderForm();
      setValidationErrors("");
      setStatus("Default parameters loaded.", "ok");
    }

    async function validateState() {
      setValidationErrors("");
      const response = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params: state }),
      });

      const payload = await response.json();
      if (!response.ok) {
        const text = (payload.errors || []).map((x) => "- " + x.path + ": " + x.message).join("\\n");
        setValidationErrors(text || payload.message || "Validation failed.");
        setStatus("Validation failed.", "warn-txt");
        return false;
      }

      setStatus(payload.message || "Validation ok.", "ok");
      return true;
    }

    async function runProgram() {
      setValidationErrors("");
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params: state }),
      });
      const payload = await response.json();

      if (!response.ok) {
        if (payload.errors) {
          const text = payload.errors.map((x) => "- " + x.path + ": " + x.message).join("\\n");
          setValidationErrors(text);
        } else {
          setValidationErrors(payload.message || "Run request failed.");
        }
        setStatus("Run request failed.", "warn-txt");
        return;
      }

      logsCursor = 0;
      logLines = [];
      const logOutput = document.getElementById("log-output");
      if (logOutput.replaceChildren) {
        logOutput.replaceChildren();
      } else {
        logOutput.innerHTML = "";
      }
      setStatus(payload.message || "Program started.", "ok");
    }

    async function stopProgram() {
      const response = await fetch("/api/stop", { method: "POST" });
      const payload = await response.json();
      if (!response.ok) {
        setStatus(payload.message || "Failed to stop process.", "warn-txt");
        return;
      }
      setStatus(payload.message || "Stop requested.", "warn-txt");
    }

    async function pollRuntime() {
      try {
        const statusResponse = await fetch("/api/status");
        const statusPayload = await statusResponse.json();

        document.getElementById("run-running").textContent = statusPayload.running ? "yes" : "no";
        document.getElementById("run-running").className = statusPayload.running ? "ok" : "muted";
        document.getElementById("run-exit").textContent = statusPayload.exit_code === null ? "-" : String(statusPayload.exit_code);
        document.getElementById("run-started").textContent = statusPayload.started_at || "-";
        document.getElementById("run-finished").textContent = statusPayload.finished_at || "-";
        setPathValue("run-params", statusPayload.last_params_path || "");

        document.getElementById("btn-run").disabled = Boolean(statusPayload.running);
        document.getElementById("btn-stop").disabled = !Boolean(statusPayload.running);

        const logsResponse = await fetch("/api/logs?from=" + logsCursor);
        const logsPayload = await logsResponse.json();
        appendLogs(logsPayload.lines || []);
        logsCursor = logsPayload.next_cursor || logsCursor;
      } catch (_err) {
        // Keep polling even if one request fails.
      }
    }

    function downloadCurrentState() {
      const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "parameters.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setStatus("JSON downloaded.", "ok");
    }

    function importJsonFromFile(file) {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const parsed = JSON.parse(reader.result);
          if (!isObject(parsed)) {
            throw new Error("JSON root must be an object.");
          }
          if (!("path_json" in parsed)) {
            parsed.path_json = state.path_json || "/app/source/parameters";
          }
          state = parsed;
          renderForm();
          setValidationErrors("");
          setStatus("JSON imported.", "ok");
        } catch (err) {
          setStatus("Import failed.", "warn-txt");
          setValidationErrors(String(err));
        }
      };
      reader.readAsText(file);
    }

    document.getElementById("btn-import").addEventListener("click", () => {
      document.getElementById("import-input").click();
    });

    document.getElementById("import-input").addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      if (!file) {
        return;
      }
      importJsonFromFile(file);
      event.target.value = "";
    });

    document.getElementById("btn-default").addEventListener("click", () => {
      loadDefaultFromServer();
    });
    document.getElementById("btn-validate").addEventListener("click", () => {
      validateState();
    });
    document.getElementById("btn-run").addEventListener("click", () => {
      runProgram();
    });
    document.getElementById("btn-stop").addEventListener("click", () => {
      stopProgram();
    });
    document.getElementById("btn-download").addEventListener("click", () => {
      downloadCurrentState();
    });

    try {
      renderForm();
      if (!PATH_PICKER_AVAILABLE && PATH_PICKER_MESSAGE) {
        setStatus(PATH_PICKER_MESSAGE, "warn-txt");
      }
      pollRuntime();
      setInterval(pollRuntime, 1200);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus("UI initialization failed: " + msg, "warn-txt");
      setValidationErrors("UI initialization failed:\\n" + msg);
    }
  </script>
</body>
</html>
"""


SCRIPT_DIR = Path(__file__).resolve().parent
PUBLISHER_SCRIPT = SCRIPT_DIR / "publisher.py"


def resolve_default_json_path() -> Path | None:
    candidates = [
        SCRIPT_DIR.parent / "source" / "default.json",
        Path("/app/source/default.json"),
        Path("/app/publisher/source/default.json"),
        Path.cwd() / "publisher" / "source" / "default.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_template_json_path() -> Path | None:
    candidates = [
        SCRIPT_DIR.parent / "source" / "parameters2.json",
        Path("/app/source/parameters2.json"),
        Path("/app/publisher/source/parameters2.json"),
        Path.cwd() / "publisher" / "source" / "parameters2.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def blank_template(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: blank_template(child) for key, child in value.items()}
    if isinstance(value, list):
        return []
    if isinstance(value, bool):
        return False
    return None


def load_default_params() -> dict[str, Any]:
    params_path = resolve_default_json_path()
    if params_path and params_path.exists():
        with params_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Default parameters file root must be a JSON object.")
        if "path_json" not in data:
            data["path_json"] = "/app/source/parameters"
        return data

    template_path = resolve_template_json_path()
    if template_path and template_path.exists():
        with template_path.open("r", encoding="utf-8") as file:
            template = json.load(file)
        if not isinstance(template, dict):
            raise ValueError("Template parameters file root must be a JSON object.")
        data = blank_template(template)
        if "path_json" not in data:
            data["path_json"] = "/app/source/parameters"
        return data

    return {"path_json": "/app/source/parameters"}


def parse_request_params(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and "params" in payload:
        params = payload["params"]
    else:
        params = payload
    if not isinstance(params, dict):
        raise ValueError("Request must provide a JSON object in 'params'.")
    if "path_json" not in params:
        params["path_json"] = "/app/source/parameters"
    return params


def validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    errors = []
    for err in exc.errors():
        path = ".".join(str(item) for item in err.get("loc", []))
        message = err.get("msg", "validation error")
        errors.append({"path": path, "message": message})
    return errors


def save_used_params(params: dict[str, Any], model: ParametersV2) -> Path:
    out_dir = Path(model.path_json).expanduser()
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"used_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with out_file.open("w", encoding="utf-8") as file:
        json.dump(params, file, indent=4, ensure_ascii=False)
    return out_file


def _suggest_initial_path(current_value: str) -> str:
    if not current_value:
        return ""
    candidate = Path(current_value).expanduser()
    if candidate.exists():
        if candidate.is_file():
            return str(candidate.parent)
        return str(candidate)
    if candidate.parent.exists():
        return str(candidate.parent)
    return ""


def _pick_path_windows(mode: str, current_value: str) -> str:
    initial = _suggest_initial_path(current_value).replace("'", "''")
    if mode == "file":
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dlg = New-Object System.Windows.Forms.OpenFileDialog; "
            "$dlg.CheckFileExists = $true; "
            "$dlg.Multiselect = $false; "
            f"$initial = '{initial}'; "
            "if($initial -and (Test-Path $initial)){ $dlg.InitialDirectory = $initial }; "
            "if($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){ Write-Output $dlg.FileName }"
        )
    else:
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dlg = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$dlg.ShowNewFolderButton = $true; "
            f"$initial = '{initial}'; "
            "if($initial -and (Test-Path $initial)){ $dlg.SelectedPath = $initial }; "
            "if($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){ Write-Output $dlg.SelectedPath }"
        )

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"Windows path picker failed: {stderr or 'unknown error'}")

    return (result.stdout or "").strip()


def _pick_path_tk(mode: str, current_value: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"Tk path picker is not available: {exc}") from exc

    initial = _suggest_initial_path(current_value)
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if mode == "file":
            return filedialog.askopenfilename(initialdir=initial or None) or ""
        return filedialog.askdirectory(initialdir=initial or None) or ""
    finally:
        root.destroy()


def path_picker_capability() -> tuple[bool, str]:
    if os.name == "nt":
        return True, ""

    if not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY"):
        return False, "Path picker unavailable in headless environment. Type the path manually."

    try:
        import tkinter as _  # noqa: F401
    except Exception as exc:
        return False, f"Tk path picker is not available: {exc}. Type the path manually."

    return True, ""


def pick_path_dialog(mode: str, current_value: str) -> str:
    if mode not in {"dir", "file"}:
        raise ValueError("mode must be 'dir' or 'file'.")

    available, message = path_picker_capability()
    if not available:
        raise RuntimeError(message)

    if os.name == "nt":
        return _pick_path_windows(mode, current_value)

    return _pick_path_tk(mode, current_value)


class ProcessRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._logs: list[str] = []
        self._running = False
        self._exit_code: int | None = None
        self._started_at: str | None = None
        self._finished_at: str | None = None
        self._last_params_path: str | None = None

    def _append(self, line: str) -> None:
        with self._lock:
            self._logs.append(line)

    def start(self, params_path: Path) -> tuple[bool, str]:
        with self._lock:
            if self._running:
                return False, "A run is already in progress."

            self._logs = []
            self._running = True
            self._exit_code = None
            self._started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._finished_at = None
            self._last_params_path = str(params_path)

            self._thread = threading.Thread(
                target=self._worker,
                args=(params_path,),
                daemon=True,
            )
            self._thread.start()
            return True, "Program started."

    def _worker(self, params_path: Path) -> None:
        command = [
            sys.executable,
            "-u",
            str(PUBLISHER_SCRIPT),
            "--params",
            str(params_path),
        ]
        self._append("$ " + " ".join(command))
        exit_code = -1
        try:
            popen_kwargs: dict[str, Any] = {
                "cwd": str(SCRIPT_DIR),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "bufsize": 1,
            }
            if os.name == "nt":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["preexec_fn"] = os.setsid

            proc = subprocess.Popen(command, **popen_kwargs)
            with self._lock:
                self._process = proc

            if proc.stdout is not None:
                for line in proc.stdout:
                    self._append(line.rstrip("\n"))

            exit_code = proc.wait()
        except Exception as exc:
            self._append(f"[runner error] {exc}")
        finally:
            with self._lock:
                self._running = False
                self._exit_code = exit_code
                self._finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._process = None
                self._logs.append(f"[process finished with code {exit_code}]")

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            if not self._running or self._process is None:
                return False, "No active process."
            proc = self._process
            self._logs.append("[termination requested]")

        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception as exc:
                return False, f"Could not terminate process: {exc}"

        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "nt":
                    proc.kill()
                else:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            return True, "Stop requested. Force kill was applied."

        return True, "Stop requested."

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "exit_code": self._exit_code,
                "started_at": self._started_at,
                "finished_at": self._finished_at,
                "last_params_path": self._last_params_path,
            }

    def logs(self, cursor: int) -> tuple[list[str], int]:
        with self._lock:
            safe_cursor = max(0, min(cursor, len(self._logs)))
            lines = self._logs[safe_cursor:]
            next_cursor = len(self._logs)
            return lines, next_cursor


app = Flask(__name__)
runner = ProcessRunner()


@app.get("/")
def index():
    params = load_default_params()
    picker_available, picker_message = path_picker_capability()
    return render_template_string(
        TEMPLATE,
        initial_state=params,
        help_text=HELP_TEXT,
        top_order=TOP_LEVEL_ORDER,
        path_picker_available=picker_available,
        path_picker_message=picker_message,
    )


@app.get("/api/default")
def api_default():
    try:
        return jsonify({"ok": True, "params": load_default_params()})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


@app.post("/api/pick-path")
def api_pick_path():
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode", "dir")).lower()
    current = str(payload.get("current", ""))

    try:
        selected_path = pick_path_dialog(mode, current)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 409
    except Exception as exc:
        return jsonify({"ok": False, "message": f"Unexpected picker error: {exc}"}), 500

    return jsonify(
        {
            "ok": True,
            "path": selected_path,
            "cancelled": selected_path == "",
        }
    )


@app.post("/api/validate")
def api_validate():
    payload = request.get_json(silent=True)
    try:
        params = parse_request_params(payload)
        ParametersV2(**params)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except ValidationError as exc:
        return jsonify({"ok": False, "errors": validation_errors(exc)}), 400

    return jsonify({"ok": True, "message": "Parameters are valid."})


@app.post("/api/run")
def api_run():
    payload = request.get_json(silent=True)
    try:
        params = parse_request_params(payload)
        model = ParametersV2(**params)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except ValidationError as exc:
        return jsonify({"ok": False, "errors": validation_errors(exc)}), 400

    try:
        used_params_path = save_used_params(params, model)
    except Exception as exc:
        return jsonify({"ok": False, "message": f"Could not save used parameters: {exc}"}), 500

    ok, message = runner.start(used_params_path)
    if not ok:
        return jsonify({"ok": False, "message": message}), 409

    return jsonify({"ok": True, "message": message, "used_params_path": str(used_params_path)})


@app.post("/api/stop")
def api_stop():
    ok, message = runner.stop()
    if not ok:
        return jsonify({"ok": False, "message": message}), 409
    return jsonify({"ok": True, "message": message})


@app.get("/api/status")
def api_status():
    return jsonify(runner.status())


@app.get("/api/logs")
def api_logs():
    raw_cursor = request.args.get("from", "0")
    try:
        cursor = int(raw_cursor)
    except ValueError:
        cursor = 0
    lines, next_cursor = runner.logs(cursor)
    return jsonify({"lines": lines, "next_cursor": next_cursor})


def maybe_open_browser(url: str) -> None:
    if os.getenv("PARAMS_WEB_OPEN_BROWSER", "1").strip().lower() in {"0", "false", "no"}:
        return

    def _open():
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            # Containerized/headless environments may not have a browser available.
            pass

    threading.Timer(1.0, _open).start()


def main():
    host = os.getenv("PARAMS_WEB_HOST", "0.0.0.0")
    port = int(os.getenv("PARAMS_WEB_PORT", "8000"))
    public_url = f"http://localhost:{port}/"
    print(f"Starting Parameters Web UI on {public_url}")
    maybe_open_browser(public_url)
    serve(app, host=host, port=port, threads=8)


if __name__ == "__main__":
    main()



