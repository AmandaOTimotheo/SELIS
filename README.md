# SELIS - Smart Energy Lighting Infrastructure Simulator

SELIS - Smart Energy Lighting Infrastructure Simulator is a Python-based simulation and analytics platform for smart public lighting scenarios.  
It models panel and edge/fog devices, simulates electrical behavior, publishes real-time MQTT data, and generates clustering, financial, and reporting outputs.

## Problem This Project Solves

Public lighting programs usually need to evaluate architecture, telemetry cost, and operation strategy before deployment. This project provides a reproducible pipeline to:

- model distributed lighting infrastructure from geospatial input data,
- simulate offline or real-time telemetry behavior,
- estimate communication/storage costs and CAPEX/OPEX,
- compare estimated vs simulated energy/cost outcomes.

## Core Features

- Geospatial clustering for `panel` and `edge_fog` topologies.
- Density and clustered interactive maps (Folium).
- Offline simulation with CSV persistence and report generation.
- Real-time simulation with MQTT publishing.
- Message collision analysis (Monte Carlo and Poisson).
- CAPEX/OPEX financial reports and dashboards.
- Estimated vs simulated tariff comparison and projections.
- Web-based parameter editor with JSON validation (`Pydantic`).

## Technology Stack

- Python 3.12
- Docker + Docker Compose
- MQTT (Eclipse Mosquitto)
- Flask + Waitress (web parameter UI)
- Pandas, NumPy, Matplotlib, Plotly
- Scikit-learn, Folium
- Pydantic

## Runtime Requirements

- Docker Desktop (recommended for full stack execution), or:
- Python 3.12 with pip for local execution
- Network access between publisher and MQTT broker

## Installation

### Option A: Docker (recommended)

1. Clone the repository.
2. From the project root, build and start services:

```bash
docker compose up --build
```

3. Open the parameter web UI:

```text
http://localhost:8000
```

### Option B: Local Python

1. Create and activate a virtual environment.
2. Install publisher dependencies:

```bash
pip install -r publisher/requirements.txt
```

3. Start MQTT broker (external or via Docker service).

## How To Run

### Run via Web UI

Use `publisher/scripts/parameters_web.py` (already default in Docker image):

```bash
python publisher/scripts/parameters_web.py
```

Then open `http://localhost:8000`, validate JSON parameters, and start execution.

### Run pipeline directly from CLI

```bash
python publisher/scripts/publisher.py --params publisher/source/default.json
```

If `--params` is omitted, the script attempts automatic discovery of `default.json`.

## Usage Example

1. Enable clustering and/or simulation flags in the parameter UI.
2. Click `Validate`.
3. Click `Run Program`.
4. Ensure the `results` folder and subfolders exist; create them if missing.
5. Inspect generated artifacts in mounted output folders such as:
   - `results/Clustering`
   - `results/Simulation`
   - `results/Financial`
   - `results/Collision`

## Parameters (Quick Reference)

- Default parameter file: `publisher/source/default.json`
- The web UI validates the JSON with Pydantic when you click `Validate`.
- CLI validation option:

```bash
python publisher/scripts/parameters_web.py --validate-only --params publisher/source/default.json
```

Common critical fields to review before running:

- `clustering.enable` and `simulation.enable` (feature toggles)
- `simulation.time.*` (start/end dates, step, timezone)
- `devices.panel.*` and `devices.edge_fog.*` (device counts, power, tariffs)
- `mqtt.*` (broker host, port, topic naming)
- `financial.*` (CAPEX/OPEX settings and report toggles)

If you want a baseline, start from `default.json` and change only the toggles and MQTT settings.


## License

This project is distributed under the MIT License.  
When reusing this code, keep the original copyright and attribution notice.
