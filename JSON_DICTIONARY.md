# JSON Dictionary

This dictionary is organized using the same top-level structure as `publisher/source/default.json`.

## 5.1 Root keys

- `debug`: enables `debugpy` wait-for-attach mode in `publisher.py` (port `5678`).
- `path_json`: folder where runtime parameter snapshots (`used_parameters_*.json`) are saved.
- `clustering`: clustering/map generation configuration block.
- `collision`: message collision simulation configuration block.
- `financial`: Capex/Opex, storage/transmission cost, payload, and currency configuration block.
- `simulation`: synthetic generation, time window, persistence, and run-mode configuration block.

## 5.2 `clustering`

- `clustering.clustering`: enables clustering execution.
- `clustering.final_path`: output directory for clustering artifacts.
- `clustering.generate_clustered_map`: enables clustered map generation.
- `clustering.generate_density_map`: enables raw density map generation.
- `clustering.raw_database.path`: input raw geospatial CSV.
- `clustering.raw_database.fields.*`: mapping from logical fields (`id`, `lat`, `lon`, `rated_*`) to CSV column names.
- `clustering.raw_database.labels.*`: labels shown in map popups for raw points.
- `clustering.devices.edge_fog.priority`: assignment priority of edge/fog devices.
- `clustering.devices.edge_fog.percentage`: fraction of points allocated to edge/fog.
- `clustering.devices.edge_fog.max_range_km`: max grouping distance (km) for edge/fog clustering.
- `clustering.devices.edge_fog.max_points`: max points assigned per edge/fog entity.
- `clustering.devices.edge_fog.labels.*`: labels shown in edge/fog map entities.
- `clustering.devices.panel.priority`: assignment priority of panel devices.
- `clustering.devices.panel.percentage`: fraction of points allocated to panel.
- `clustering.devices.panel.n_branchs`: number of branches per panel.
- `clustering.devices.panel.min_points_branch`: minimum points per branch.
- `clustering.devices.panel.max_points_branch`: maximum points per branch.
- `clustering.devices.panel.labels.*`: labels shown in panel map entities.

## 5.3 `collision`

- `collision.enable`: enables collision analysis module.
- `collision.monte_carlo_simulation_enable`: enables Monte Carlo approach.
- `collision.poisson_calculation_enable`: enables Poisson-based calculation.
- `collision.num_edges`: number of transmitting edges considered.
- `collision.num_channels`: available communication channels.
- `collision.msg_transmission_time`: message transmission time (seconds).
- `collision.transmission_interval_edge`: interval between edge transmissions (seconds).
- `collision.t_simulation_cycles`: number of simulation cycles.
- `collision.save_data_path`: directory for collision report outputs.

## 5.4 `financial`

- `financial.general.price_kWh`: electricity price per kWh for cost calculations.
- `financial.general.save_report_path`: output directory for financial reports.
- `financial.general.used_currency`: base currency used in outputs.
- `financial.general.conversion_to_other_currency.enable`: enables conversion from base currency.
- `financial.general.conversion_to_other_currency.to`: target currency code.
- `financial.general.currency_to_USD.*`: currency conversion factors used by reporting.
- `financial.general.estimated_vs_simulated.enable`: enables estimated-vs-simulated comparison.
- `financial.general.estimated_vs_simulated.estimated_hours_on_per_day`: estimated daily on-hours for baseline calculation.
- `financial.general.estimated_vs_simulated.yellow_flag_add_price`: yellow flag surcharge parameter.
- `financial.general.estimated_vs_simulated.red_flag_1_add_price`: red flag level 1 surcharge parameter.
- `financial.general.estimated_vs_simulated.red_flag_2_add_price`: red flag level 2 surcharge parameter.
- `financial.devices.panel.communication_cost_report.enable_consumption_report`: enables simulated consumption report for panel.
- `financial.devices.panel.communication_cost_report.enable_transmission_and_storage`: enables transmission/storage cost for panel.
- `financial.devices.panel.communication_cost_report.enable_capex`: enables panel CAPEX report.
- `financial.devices.panel.communication_cost_report.enable_opex`: enables panel OPEX report.
- `financial.devices.panel.communication_cost_report.chosen_communication`: selected communication profile key for panel.
- `financial.devices.panel.communication_cost_report.communication_type.PANEL.*`: panel communication technology parameters (power, installation, maintenance, cable, per-unit costs, protocol overhead).
- `financial.devices.panel.communication_cost_report.storage.months_of_storage`: storage horizon for panel cost model.
- `financial.devices.panel.communication_cost_report.storage.storage_cost_per_GB`: storage unit cost for panel model.
- `financial.devices.panel.communication_cost_report.transmission.connectivity_cost_per_minute`: connectivity cost rate for panel.
- `financial.devices.panel.communication_cost_report.transmission.cost_per_mqtt_msg`: MQTT per-message cost for panel.
- `financial.devices.panel.communication_cost_report.transmission.max_KBs_per_message`: billing payload size threshold for panel.
- `financial.devices.panel.communication_cost_report.transmission.internet_cost_MB_BRL.*`: mobile data plan reference values.
- `financial.devices.panel.payloads.header.general.*`: output field aliases for panel general fields.
- `financial.devices.panel.payloads.header.measures.*`: output field aliases for panel measurements.
- `financial.devices.panel.payloads.n_decimals.general.*`: decimal precision for panel general fields.
- `financial.devices.panel.payloads.n_decimals.measures.*`: decimal precision for panel measurements.
- `financial.devices.panel.payloads.save.storage_format`: persistence format for panel saved payloads.
- `financial.devices.panel.payloads.save.general.*`: enable/disable each panel general field in saved payloads.
- `financial.devices.panel.payloads.save.measures.*`: enable/disable each panel measure in saved payloads.
- `financial.devices.panel.payloads.send.transmission_format`: transmission format for panel sent payloads.
- `financial.devices.panel.payloads.send.general.*`: enable/disable each panel general field in sent payloads.
- `financial.devices.panel.payloads.send.measures.*`: enable/disable each panel measure in sent payloads.
- `financial.devices.edge_fog.communication_cost_report.enable_consumption_report`: enables simulated consumption report for edge/fog.
- `financial.devices.edge_fog.communication_cost_report.enable_transmission_and_storage`: enables transmission/storage cost for edge/fog.
- `financial.devices.edge_fog.communication_cost_report.enable_capex`: enables edge/fog CAPEX report.
- `financial.devices.edge_fog.communication_cost_report.enable_opex`: enables edge/fog OPEX report.
- `financial.devices.edge_fog.communication_cost_report.chosen_communication`: selected communication profile key for edge/fog.
- `financial.devices.edge_fog.communication_cost_report.communication_type.GPRS.*`: GPRS cost/power/overhead parameters.
- `financial.devices.edge_fog.communication_cost_report.communication_type.LORA.*`: LoRa cost/power/overhead parameters.
- `financial.devices.edge_fog.communication_cost_report.storage.months_of_storage`: storage horizon for edge/fog cost model.
- `financial.devices.edge_fog.communication_cost_report.storage.storage_cost_per_GB`: storage unit cost for edge/fog model.
- `financial.devices.edge_fog.communication_cost_report.transmission.connectivity_cost_per_minute`: connectivity cost rate for edge/fog.
- `financial.devices.edge_fog.communication_cost_report.transmission.cost_per_mqtt_msg`: MQTT per-message cost for edge/fog.
- `financial.devices.edge_fog.communication_cost_report.transmission.max_KBs_per_message`: billing payload size threshold for edge/fog.
- `financial.devices.edge_fog.communication_cost_report.transmission.internet_cost_MB_BRL.*`: mobile data plan reference values.
- `financial.devices.edge_fog.payloads.header.general.*`: output field aliases for edge/fog general fields.
- `financial.devices.edge_fog.payloads.header.measures.*`: output field aliases for edge/fog measurements.
- `financial.devices.edge_fog.payloads.n_decimals.general.*`: decimal precision for edge/fog general fields.
- `financial.devices.edge_fog.payloads.n_decimals.measures.*`: decimal precision for edge/fog measurements.
- `financial.devices.edge_fog.payloads.save.storage_format`: persistence format for edge/fog saved payloads.
- `financial.devices.edge_fog.payloads.save.general.*`: enable/disable each edge/fog general field in saved payloads.
- `financial.devices.edge_fog.payloads.save.measures.*`: enable/disable each edge/fog measure in saved payloads.
- `financial.devices.edge_fog.payloads.send.transmission_format`: transmission format for edge/fog sent payloads.
- `financial.devices.edge_fog.payloads.send.general.*`: enable/disable each edge/fog general field in sent payloads.
- `financial.devices.edge_fog.payloads.send.measures.*`: enable/disable each edge/fog measure in sent payloads.

## 5.5 `simulation`

- `simulation.window.use_current_time_and_date`: uses current system date/time instead of manual window.
- `simulation.window.simulation_start_date`: simulation start date (`MM/DD/YYYY`).
- `simulation.window.simulation_start_time`: simulation start time (`HH:MM`).
- `simulation.window.simulation_stop_date`: simulation stop date (`MM/DD/YYYY`).
- `simulation.window.simulation_stop_time`: simulation stop time (`HH:MM`).
- `simulation.window.time_zone`: timezone used in date/time logic.
- `simulation.daylight.sunrise_start`: sunrise interval start used by day/night behavior.
- `simulation.daylight.sunrise_end`: sunrise interval end.
- `simulation.daylight.sunset_start`: sunset interval start.
- `simulation.daylight.sunset_end`: sunset interval end.
- `simulation.generation.voltage.v_upper_variation`: upper variation factor for voltage synthesis.
- `simulation.generation.voltage.v_lower_variation`: lower variation factor for voltage synthesis.
- `simulation.generation.current.c_upper_variation`: upper variation factor for current synthesis.
- `simulation.generation.current.c_lower_variation`: lower variation factor for current synthesis.
- `simulation.generation.consumption.power_factor_variation`: variation factor for power factor/consumption generation.
- `simulation.persistence.save_simulation_data`: enables persistence of generated simulation data.
- `simulation.persistence.csv_lines_limit`: max CSV lines before rotating/splitting output files.
- `simulation.devices.panel.publication_interval_day`: panel publication interval in daytime.
- `simulation.devices.panel.publication_interval_night`: panel publication interval in nighttime.
- `simulation.devices.panel.database.path`: panel input CSV path.
- `simulation.devices.panel.database.fields.*`: panel CSV logical-to-column mapping.
- `simulation.devices.panel.failure_rate.day_on`: daytime failure probability for panel.
- `simulation.devices.panel.failure_rate.night_low_voltage`: low-voltage probability at night for panel.
- `simulation.devices.panel.failure_rate.night_zero_voltage`: zero-voltage probability at night for panel.
- `simulation.devices.panel.failure_rate.transmission`: transmission failure probability for panel.
- `simulation.devices.panel.modes.offline_simulation.enable`: enables panel offline simulation mode.
- `simulation.devices.panel.modes.offline_simulation.save_data_path`: panel offline output directory.
- `simulation.devices.panel.modes.real_time_simulation.enable`: enables panel real-time mode.
- `simulation.devices.panel.modes.real_time_simulation.is_print_publish`: prints every published panel payload.
- `simulation.devices.panel.modes.real_time_simulation.topics`: MQTT publish topic for panel.
- `simulation.devices.panel.modes.real_time_simulation.mqtt.broker_address`: MQTT broker host for panel.
- `simulation.devices.panel.modes.real_time_simulation.mqtt.broker_port`: MQTT broker port for panel.
- `simulation.devices.edge_fog.publication_interval_day`: edge/fog publication interval in daytime.
- `simulation.devices.edge_fog.publication_interval_night`: edge/fog publication interval in nighttime.
- `simulation.devices.edge_fog.database.path`: edge/fog input CSV path.
- `simulation.devices.edge_fog.database.fields.*`: edge/fog CSV logical-to-column mapping.
- `simulation.devices.edge_fog.failure_rate.day_on`: daytime failure probability for edge/fog.
- `simulation.devices.edge_fog.failure_rate.night_low_voltage`: low-voltage probability at night for edge/fog.
- `simulation.devices.edge_fog.failure_rate.night_zero_voltage`: zero-voltage probability at night for edge/fog.
- `simulation.devices.edge_fog.failure_rate.transmission`: transmission failure probability for edge/fog.
- `simulation.devices.edge_fog.modes.offline_simulation.enable`: enables edge/fog offline simulation mode.
- `simulation.devices.edge_fog.modes.offline_simulation.save_data_path`: edge/fog offline output directory.
- `simulation.devices.edge_fog.modes.real_time_simulation.enable`: enables edge/fog real-time mode.
- `simulation.devices.edge_fog.modes.real_time_simulation.is_print_publish`: prints every published edge/fog payload.
- `simulation.devices.edge_fog.modes.real_time_simulation.topics`: MQTT publish topic for edge/fog.
- `simulation.devices.edge_fog.modes.real_time_simulation.mqtt.broker_address`: MQTT broker host for edge/fog.
- `simulation.devices.edge_fog.modes.real_time_simulation.mqtt.broker_port`: MQTT broker port for edge/fog.
