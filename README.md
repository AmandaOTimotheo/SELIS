# SELIS - Smart Energy & Lighting Infrastructure Simulator

### V1.0, February, 2026

**Authors:** Amanda O. Timotheo, Humberto A. Guimarães, Iago Z. Biundini, Mario A. R. Dantas, Miriam A. M. Capretz, Leonardo M. Honório.

SELIS (Smart Energy & Lighting Infrastructure Simulator) is a containerized, modular simulation framework for planning, operating, and modernizing public lighting systems. It supports the evaluation of centralized (Panel) and decentralized (Edge/Fog) architectures by integrating geospatial clustering, synthetic data generation, communication emulation, and financial analysis to support scenario-based studies and decision-making.

## Related Publications:

Amanda O. Timotheo, Humberto A. Guimarães, Iago Z. Biundini, Mario A. R. Dantas, Miriam A. M. Capretz and Leonardo M. Honório, **SELIS: A Smart Energy & Lighting Infrastructure Simulator — Software Architecture and Design**, *SoftwareX* (submitted, 2026).

# 1. License

Shield: [![CC BY-NC-ND 4.0][cc-by-nc-nd-shield]][cc-by-nc-nd]

SELIS is released under the
[Creative Commons Attribution-NonCommercial-NoDerivs 4.0 International License][cc-by-nc-nd].

[![CC BY-NC-ND 4.0][cc-by-nc-nd-image]][cc-by-nc-nd]

[cc-by-nc-nd]: http://creativecommons.org/licenses/by-nc-nd/4.0/
[cc-by-nc-nd-image]: https://licensebuttons.net/l/by-nc-nd/4.0/88x31.png
[cc-by-nc-nd-shield]: https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg

If you use SELIS in an academic work, please cite:

    @article{SELIS,
      title   = {{SELIS}: A Smart Energy \& Lighting Infrastructure Simulator - Software Architecture and Design},
      author  = {Timotheo, Amanda O. and Guimarães, Humberto A. and Biundini, Iago Z. and Dantas, Mario A. R. and Capretz, Miriam A. M. and Honório, Leonardo M.},
      journal = {SoftwareX},
      year    = {2026},
      note    = {submitted}
    }


# 2. Prerequisites

We have tested SELIS primarily with **Docker Desktop** on **Windows 10/11**. Since SELIS runs in a container, it should also work without issues on other operating systems that support Docker.

## Docker Desktop
Download and install instructions can be found at: https://docs.docker.com/get-started/get-docker/

## IDE (Optional)
We recommend Visual Studio Code as the IDE for editing and debugging.

Download and install Visual Studio Code at: https://code.visualstudio.com/

# Building SELIS

## Option A: Using an IDE (Visual Studio Code)

1. Open the repository page: https://github.com/AmandaOTimotheo/SELIS
2. Click `Code` > `Download ZIP`.
3. Extract the ZIP file.
4. Open Visual Studio Code.
5. Go to `File` > `Open Folder` and select the extracted `SELIS` folder.
6. Open Docker Desktop and wait until Docker is running.
7. In the VS Code terminal, run:
```
docker compose up --build
```

## Option B: Without an IDE (Terminal only)

1. Clone the repository:
```
git clone https://github.com/AmandaOTimotheo/SELIS.git
cd SELIS
```
2. Open Docker Desktop and wait until Docker is running.
3. In the terminal run:
```
docker compose up --build
```

The command above builds SELIS containers, installs Python 3.12, and installs the required libraries from `requirements.txt`.

# Running SELIS

## 1. Start the services and open the Web UI

After the build and startup, the publisher container prints:

```text
Starting Parameters Web UI on http://localhost:8000/
```

Open this link to access the parameters interface.

## 2. Configure the JSON parameters

SELIS uses the parameters model defined in `publisher/source/default.json`.

You can configure it in two ways:

1. Directly in the Web UI form:
   Edit the fields, then `Run Program`.
2. By editing a `.json` file manually:
   Edit a JSON file with the same schema, import it in the Web UI (`Import JSON`), click `Validate`, then `Run Program`.

When you click `Run Program`, the Web API runs a full validation of parameters and saves the effective runtime file as:

`used_parameters_YYYYMMDD_HHMMSS.json` in `path_json` (default: `/app/source/parameters`).

## 3. Main functions

### `clustering`

- What it does: organizes raw geospatial streetlights data into panel and edge/fog groups, and can generate visualization maps.
- Return: grouped device datasets used by the next pipeline stages.
- Where output is produced: `clustering.final_path`.
- Output structure/format: clustered data files (CSV) and map files (HTML).

### `collision`

- What it does: estimates message-collision behavior using channel count, transmission interval, and simulation cycles.
- Return: collision analysis metrics/report content.
- Where output is produced: `collision.save_data_path`.
- Output structure/format: collision report files (CSV).

### `financial`

- What it does: computes financial analyses (for example Capex/Opex, communication, storage, and energy costs).
- Return: per-device and/or combined financial results for panel and edge/fog.
- Where output is produced: `financial.general.save_report_path`.
- Output structure/format: report files (CSV, XLSX), charts (PNG), and dashboards (HTML).

### `simulation`

- What it does: generates operational data for panel and edge/fog in offline mode and/or real-time mode.
- Return: offline simulated datasets and/or live publication streams.
- Where output is produced: offline files in each device `offline_simulation.save_data_path`; real-time in configured MQTT topics (`panel/pub`, `fog/pub`, or custom topics).
- Output structure/format: streetlights states and/or general simulation results in report files (CSV).

## 4. Debug mode (VS Code + Docker)

To debug `publisher.py` inside Docker:

1. In the Web UI parameters, set `debug: true`.
2. Click `Run Program`.
3. The process will wait on `debugpy` at port `5678`.
4. In VS Code, create/edit `.vscode/launch.json` with:

```json
{
  "version": "0.2.0",
  "log": true,
  "configurations": [
    
    {
      "name": "Python: Attach to Docker",
      "type": "debugpy",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/publisher/scripts",
          "remoteRoot": "/app/publisher"
        }
      ]
    }
  ]
}
```

5. In VS Code Run and Debug, choose `Python: Attach to Docker` and press Play.

## 5. JSON dictionary

Dictionary for `publisher/source/default.json`: [JSON_DICTIONARY.md](./JSON_DICTIONARY.md)
