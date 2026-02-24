from __future__ import annotations
"""Pydantic model definitions for the full Generator_Math configuration schema."""

from datetime import date, time, datetime, timedelta
from typing import Dict, Literal, Optional, Annotated, Union
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    NonNegativeFloat,
    field_validator,
    model_validator,
    computed_field,
)


# ----------------------- Helpers ----------------------- #

def parse_date_dmy(value: str) -> date:
    """Parse date strings in MM/DD/YYYY format."""
    return datetime.strptime(value, "%m/%d/%Y").date()

def parse_time_hm(value: str) -> time:
    """Parse time strings in HH:MM format."""
    return datetime.strptime(value, "%H:%M").time()


class StrictModel(BaseModel):
    """Base model with controlled parsing behavior used across all configs."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ----------------------- Collision ----------------------- #


class CollisionConfig(StrictModel):
    enable: bool
    save_data_path: Optional[str] = None
    num_edges: PositiveInt
    msg_transmission_time: NonNegativeFloat
    t_simulation_cycles: PositiveInt
    transmission_interval_edge: PositiveInt
    num_channels: PositiveInt
    poisson_calculation_enable: bool
    monte_carlo_simulation_enable: bool

    @model_validator(mode="after")
    def validate_collision_parameters(self):
        if self.enable and not self.save_data_path:
            raise ValueError("When 'collision.enable' is True, provide 'save_data_path' to store the report.")

        if self.enable and not (self.poisson_calculation_enable or self.monte_carlo_simulation_enable):
            raise ValueError("When 'collision.enable' is True, set at least one of poisson_calculation_enable or monte_carlo_simulation_enable to True.")

        if self.poisson_calculation_enable:
            if not (self.msg_transmission_time <= self.transmission_interval_edge and self.num_edges > 0):
                raise ValueError(
                    "When Poisson collision analysis is enabled, ensure msg_transmission_time <= transmission_interval_edge and num_edges > 0."
                )
            if not self.save_data_path:
                raise ValueError("Provide 'save_data_path' when Poisson collision analysis is enabled.")

        if self.monte_carlo_simulation_enable:
            if self.num_channels < 1:
                raise ValueError("When Monte Carlo collision simulation is enabled, ensure num_channels >= 1.")
            if self.num_edges <= 0:
                raise ValueError("When Monte Carlo collision simulation is enabled, ensure num_edges > 0.")
            if not self.save_data_path:
                raise ValueError("Provide 'save_data_path' when Monte Carlo collision simulation is enabled.")

        return self


# ----------------------- Common Simulation Fields ----------------------- #


class CommonFields(StrictModel):
    id: str
    lat: str
    lon: str
    lat_cell: str
    lon_cell: str
    cluster_name: str
    rated_power: str
    rated_voltage: str
    rated_power_factor: str
    rated_current: str
    name: str


class PanelFields(CommonFields):
    panel_num: str
    branch_num: str
    panel_id: str


class EdgeFogFields(CommonFields):
    fog_num: str
    edge_num: str
    is_fog: str
    fog_id: str
    edge_id: str


class SimulationDatabaseConfig(StrictModel):
    path: str
    fields: Union[PanelFields, EdgeFogFields]


# ----------------------- Clustering ----------------------- #


class RawDatabaseFields(StrictModel):
    id: str
    lat: str
    lon: str
    rated_power: str
    rated_voltage: str
    rated_power_factor: str


class RawDatabaseConfig(StrictModel):
    path: str
    fields: RawDatabaseFields
    labels: Dict[str, str]


class ClusteringPanelConfig(StrictModel):
    priority: PositiveInt
    percentage: NonNegativeFloat
    n_branchs: PositiveInt
    min_points_branch: PositiveInt
    max_points_branch: PositiveInt
    labels: Dict[str, str]


class ClusteringEdgeFogConfig(StrictModel):
    priority: PositiveInt
    percentage: NonNegativeFloat
    max_range_km: NonNegativeFloat
    max_points: PositiveInt
    labels: Dict[str, str]


class ClusteringDevicesConfig(StrictModel):
    panel: ClusteringPanelConfig
    edge_fog: ClusteringEdgeFogConfig


class ClusteringConfig(StrictModel):
    raw_database: RawDatabaseConfig
    final_path: str
    interactive_map_path: Optional[str] = None
    clustering: bool
    generate_density_map: bool
    generate_clustered_map: bool
    devices: ClusteringDevicesConfig

    @model_validator(mode="after")
    def validate_raw_database_dependency(self):
        """
        Ensures that 'raw_database' is provided (with path and fields)
        when either 'generate_density_map' or 'clustering' is True.
        """
        if self.generate_density_map or self.clustering or self.generate_clustered_map:
            if not self.raw_database:
                raise ValueError(
                    "The 'raw_database' must be provided inside 'clustering' "
                    "when 'generate_density_map' or 'clustering' or 'generate_clustered_map' is True."
                )
            if not self.raw_database.path:
                raise ValueError(
                    "The 'raw_database.path' must be provided when "
                    "'generate_density_map' or 'clustering' or 'generate_clustered_map' is True."
                )
            if not self.raw_database.fields:
                raise ValueError(
                    "The 'raw_database.fields' must be provided when "
                    "'generate_density_map' or 'clustering' or 'generate_clustered_map' is True."
                )

        if self.generate_density_map:
            if not self.raw_database.labels:
                raise ValueError(
                    "Provide 'clustering.raw_database.labels' when 'generate_density_map' is True."
                )

        total_percentage = sum(
            device.percentage
            for device in self.devices.__dict__.values()
            if hasattr(device, "percentage")
        )
        if abs(total_percentage - 1.0) > 1e-6:
            raise ValueError(
                "The sum of clustering.devices percentages must be 1.0 (100%)."
            )

        return self

# ----------------------- Simulation ----------------------- #
       

class OfflineSimulationConfig(StrictModel):
    enable: bool
    save_data_path: Optional[str] = None


class RealTimeSimulationConfig(StrictModel):
    enable: bool
    is_print_publish: bool
    mqtt: MQTTConfig
    topics: str


class SimulationModes(StrictModel):
    offline_simulation: OfflineSimulationConfig
    real_time_simulation: RealTimeSimulationConfig

    @model_validator(mode="after")
    def check_simulation_realtime_conflict(self):
        if self.offline_simulation.enable and self.real_time_simulation.enable:
            raise ValueError(
                "Both 'offline_simulation.enable' and 'real_time_simulation.enable' cannot be True at the same time."
            )
        return self
    
class SimulationWindow(StrictModel):
    use_current_time_and_date: bool
    simulation_start_date: date
    simulation_start_time: time
    time_zone: str
    simulation_stop_date: date
    simulation_stop_time: time

    @field_validator("simulation_start_date", "simulation_stop_date", mode="before")
    @classmethod
    def _parse_dates(cls, v):
        if isinstance(v, date):
            return v
        return parse_date_dmy(v)

    @field_validator("simulation_start_time", "simulation_stop_time", mode="before")
    @classmethod
    def _parse_times(cls, v):
        if isinstance(v, time):
            return v
        return parse_time_hm(v)

    @computed_field
    @property
    def simulation_start_dt(self) -> Optional[datetime]:
        if self.use_current_time_and_date:
            return None
        return datetime.combine(self.simulation_start_date, self.simulation_start_time)

    @computed_field
    @property
    def simulation_stop_dt(self) -> Optional[datetime]:
        if self.use_current_time_and_date:
            return None
        return datetime.combine(self.simulation_stop_date, self.simulation_stop_time)

    def simulation_duration(self) -> Optional[timedelta]:
        if self.use_current_time_and_date:
            return None
        return self.simulation_stop_dt - self.simulation_start_dt

    @model_validator(mode="after")
    def check_dates_order(self):
        if not self.use_current_time_and_date:
            if self.simulation_stop_dt <= self.simulation_start_dt:
                raise ValueError("simulation_stop_dt must be higher than simulation_start_dt.")
        return self


class PersistenceConfig(StrictModel):
    save_simulation_data: bool
    csv_lines_limit: PositiveInt


class SimulationDevices(StrictModel):
    panel: SimulationConfig
    edge_fog: SimulationConfig


class Simulation(StrictModel):
    devices: SimulationDevices
    window: SimulationWindow
    persistence: PersistenceConfig
    generation: GenerationConfig
    daylight: DaylightWindowConfig
    
    @model_validator(mode="after")
    def validate_consistency_between_panel_and_edge_fog(self):
        COMMON_REQUIRED_FIELDS = [
            "id", "lat", "lon", "lat_cell", "lon_cell", "cluster_name",
            "rated_power", "rated_voltage", "rated_power_factor", "rated_current"
        ]

        p = self.devices.panel.database.fields
        e = self.devices.edge_fog.database.fields

        for field in COMMON_REQUIRED_FIELDS:
            pv = getattr(p, field)
            ev = getattr(e, field)

            if pv != ev:
                raise ValueError(
                    f"The field '{field}' is not consistent between panel and edge_fog.\n"
                    f"Panel has: '{pv}'   Edge_Fog has: '{ev}'"
                )

        return self

    @model_validator(mode="after")
    def validate_save_paths_conditionally(self):

        devices = self.devices
        # get devices names iteractively
        dev_names = type(devices).model_fields.keys()
        for dev_name in dev_names:
            device = getattr(devices, dev_name)
            modes = device.modes
            if modes.offline_simulation.enable and not modes.offline_simulation.save_data_path:
                raise ValueError(
                    f"Provide 'save_data_path' for simulation.devices.{dev_name}.modes.offline_simulation when offline simulation is enabled."
                )

        return self
    
class SimulationConfig(StrictModel):
    modes: SimulationModes
    publication_interval_day: PositiveInt
    publication_interval_night: PositiveInt
    failure_rate: FailureRateConfig
    database: SimulationDatabaseConfig


class FailureRateConfig(StrictModel):
    day_on: NonNegativeFloat
    night_low_voltage: NonNegativeFloat
    night_zero_voltage: NonNegativeFloat
    transmission: NonNegativeFloat
    
class CommunicationPricingPanel(StrictModel):
    price_per_panel: NonNegativeFloat
    price_panel_installation: NonNegativeFloat
    price_cable_meter: NonNegativeFloat
    price_cable_installation_meter: NonNegativeFloat
    price_panel_annual_maintenance: NonNegativeFloat
    panel_power_W: NonNegativeFloat
    overhead_bytes: PositiveInt


class CommunicationPricingEdgeFog(StrictModel):
    price_per_fog: NonNegativeFloat
    price_fog_installation: NonNegativeFloat
    price_per_edge: NonNegativeFloat
    price_edge_installation: NonNegativeFloat
    price_fog_annual_maintenance: NonNegativeFloat
    price_edge_annual_maintenance: NonNegativeFloat
    fog_power_W: NonNegativeFloat
    edge_power_W: NonNegativeFloat
    overhead_bytes: PositiveInt

class CommunicationCostsCommon(StrictModel):
    enable_consumption_report: bool
    enable_transmission_and_storage: bool
    enable_capex: bool
    enable_opex: bool
    storage: StorageCostsConfig
    transmission: TransmissionCostsConfig
    chosen_communication: str
    
class CommunicationCostReportPanel(CommunicationCostsCommon):
    communication_type: Dict[str, CommunicationPricingPanel]
    @model_validator(mode="after")
    def validate_chosen_communication(self):
        if not self.communication_type or not self.chosen_communication:
            return self
        if self.chosen_communication not in self.communication_type:
            raise ValueError(
                f"chosen_communication '{self.chosen_communication}' not found in communication_type. "
                f"Available options: {list(self.communication_type.keys())}"
            )
        return self

    @computed_field
    @property
    def active_communication(self) -> CommunicationPricingPanel:
        return self.communication_type[self.chosen_communication]

    @computed_field
    @property
    def storage_price_per_MB(self) -> float:
        return self.storage.storage_cost_per_GB / 1024


class CommunicationCostReportEdgeFog(CommunicationCostsCommon):
    communication_type: Dict[str, CommunicationPricingEdgeFog]

    @model_validator(mode="after")
    def validate_chosen_communication(self):
        if not self.communication_type or not self.chosen_communication:
            return self
        if self.chosen_communication not in self.communication_type:
            raise ValueError(
                f"chosen_communication '{self.chosen_communication}' not found in communication_type. "
                f"Available options: {list(self.communication_type.keys())}"
            )
        return self

    @computed_field
    @property
    def active_communication(self) -> CommunicationPricingEdgeFog:
        return self.communication_type[self.chosen_communication]

    @computed_field
    @property
    def storage_price_per_MB(self) -> float:
        return self.storage.storage_cost_per_GB / 1024


class FinancialPanelConfig(StrictModel):
    communication_cost_report: CommunicationCostReportPanel
    payloads: PayloadConfigPanel

    @computed_field
    @property
    def enable_capex(self) -> bool:
        return self.communication_cost_report.enable_capex


    @computed_field
    @property
    def enable_opex(self) -> bool:
        return self.communication_cost_report.enable_opex


    @computed_field
    @property
    def active_communication(self) -> CommunicationPricingPanel:
        return self.communication_cost_report.active_communication

    @computed_field
    @property
    def storage_price_per_MB(self) -> float:
        return self.communication_cost_report.storage_price_per_MB


class FinancialEdgeFogConfig(StrictModel):
    communication_cost_report: CommunicationCostReportEdgeFog
    payloads: PayloadConfigEdge

    @computed_field
    @property
    def enable_capex(self) -> bool:
        return self.communication_cost_report.enable_capex


    @computed_field
    @property
    def enable_opex(self) -> bool:
        return self.communication_cost_report.enable_opex


    @computed_field
    @property
    def active_communication(self) -> CommunicationPricingEdgeFog:
        return self.communication_cost_report.active_communication

    @computed_field
    @property
    def storage_price_per_MB(self) -> float:
        return self.communication_cost_report.storage_price_per_MB
# ----------------------- Financial ----------------------- #

class FinancialGeneralConfig(StrictModel):
    price_kWh: NonNegativeFloat
    used_currency: str = Field(alias="used currency")
    conversion_to_other_currency: ConversionToOtherCurrency
    currency_to_dolar: Dict[str, NonNegativeFloat] = Field(alias="currency_to_USD")
    save_report_path: str
    estimated_vs_simulated: EstimatedVsSimulatedConfig

    @computed_field
    @property
    def currency_code(self) -> str:
        return self.used_currency.upper()

    @computed_field
    @property
    def currency_symbol(self) -> str:
        symbols = {
            "BRL": "R$",
            "USD": "US$",
            "EUR": "EUR",
            "GBP": "GBP",
            "JPY": "JPY",
            "AUD": "AUD",
            "CAN": "CAN",
        }
        return symbols.get(self.currency_code, self.currency_code)

    @computed_field
    @property
    def currency_locale(self) -> str:
        if self.currency_code == "BRL":
            return "pt-BR"
        return "en-US"

class FinancialDevices(StrictModel):
    panel: FinancialPanelConfig
    edge_fog: FinancialEdgeFogConfig


class Financial(StrictModel):
    general: FinancialGeneralConfig
    devices: FinancialDevices

    @model_validator(mode="after")
    def apply_currency_conversion(self):
        conversion = self.general.conversion_to_other_currency
        if not conversion.enable:
            self.general.used_currency = self.general.used_currency.upper()
            return self

        source = self.general.used_currency.upper()
        target = conversion.to.upper()
        rates = {k.upper(): v for k, v in self.general.currency_to_dolar.items()}
        if source not in rates or target not in rates:
            raise ValueError(
                f"currency_to_USD must include both '{source}' and '{target}'."
            )

        source_rate = rates[source]
        target_rate = rates[target]
        if source_rate <= 0 or target_rate <= 0:
            raise ValueError("currency_to_USD rates must be > 0.")

        factor = target_rate / source_rate

        def _convert(value: float) -> float:
            return round(value * factor, 6)

        general = self.general
        general.price_kWh = _convert(general.price_kWh)
        general.estimated_vs_simulated.yellow_flag_add_price = _convert(
            general.estimated_vs_simulated.yellow_flag_add_price
        )
        general.estimated_vs_simulated.red_flag_1_add_price = _convert(
            general.estimated_vs_simulated.red_flag_1_add_price
        )
        general.estimated_vs_simulated.red_flag_2_add_price = _convert(
            general.estimated_vs_simulated.red_flag_2_add_price
        )

        for device in self.devices.__dict__.values():
            comm = device.communication_cost_report
            comm.storage.storage_cost_per_GB = _convert(comm.storage.storage_cost_per_GB)
            comm.transmission.connectivity_cost_per_minute = _convert(
                comm.transmission.connectivity_cost_per_minute
            )
            comm.transmission.cost_per_mqtt_msg = _convert(
                comm.transmission.cost_per_mqtt_msg
            )
            comm.transmission.internet_cost_MB_BRL = {
                k: _convert(v) for k, v in comm.transmission.internet_cost_MB_BRL.items()
            }

            for pricing in comm.communication_type.values():
                if isinstance(pricing, CommunicationPricingPanel):
                    pricing.price_per_panel = _convert(pricing.price_per_panel)
                    pricing.price_panel_installation = _convert(pricing.price_panel_installation)
                    pricing.price_cable_meter = _convert(pricing.price_cable_meter)
                    pricing.price_cable_installation_meter = _convert(pricing.price_cable_installation_meter)
                    pricing.price_panel_annual_maintenance = _convert(pricing.price_panel_annual_maintenance)
                elif isinstance(pricing, CommunicationPricingEdgeFog):
                    pricing.price_per_fog = _convert(pricing.price_per_fog)
                    pricing.price_fog_installation = _convert(pricing.price_fog_installation)
                    pricing.price_per_edge = _convert(pricing.price_per_edge)
                    pricing.price_edge_installation = _convert(pricing.price_edge_installation)
                    pricing.price_fog_annual_maintenance = _convert(pricing.price_fog_annual_maintenance)
                    pricing.price_edge_annual_maintenance = _convert(pricing.price_edge_annual_maintenance)

        general.used_currency = target
        return self


# ----------------------- MQTT / Topics ----------------------- #

class MQTTConfig(StrictModel):
    broker_address: str
    broker_port: PositiveInt


# ----------------------- Publication / Daylight ----------------------- #


class DaylightWindowConfig(StrictModel):
    sunrise_start: time
    sunrise_end: time
    sunset_start: time
    sunset_end: time

    @field_validator("sunrise_start", "sunrise_end", "sunset_start", "sunset_end", mode="before")
    @classmethod
    def _parse_time(cls, v):
        if isinstance(v, time):
            return v
        return parse_time_hm(v)


# ----------------------- Generation ----------------------- #

class VoltageGenConfig(StrictModel):
    v_upper_variation: NonNegativeFloat
    v_lower_variation: NonNegativeFloat


class CurrentGenConfig(StrictModel):
    c_upper_variation: NonNegativeFloat
    c_lower_variation: NonNegativeFloat


class ConsumptionGenConfig(StrictModel):
    power_factor_variation: NonNegativeFloat


class GenerationConfig(StrictModel):
    voltage: VoltageGenConfig
    current: CurrentGenConfig
    consumption: ConsumptionGenConfig


# ----------------------- Payloads ----------------------- #

class PanelGeneralFlags(StrictModel):
    timestamp: bool
    id: bool
    name: bool
    battery: bool
    temperature: bool
    humidity: bool
    branches_status: bool


class PanelMeasuresFlags(StrictModel):
    voltage: bool
    current: bool
    consumption: bool
    power_factor: bool
    alarm: bool

class PanelSend(StrictModel):
    transmission_format: Literal["JSON", "CBOR"]
    general: PanelGeneralFlags
    measures: PanelMeasuresFlags
    
class PanelSave(StrictModel):
    storage_format: Literal["SQL", "CSV"]
    general: PanelGeneralFlags
    measures: PanelMeasuresFlags


class PanelHeaderGeneral(StrictModel):
    timestamp: str
    id: str
    name: str
    battery: str
    temperature: str
    humidity: str
    branches_status: str


class PanelHeaderMeasures(StrictModel):
    voltage: str
    current: str
    consumption: str
    power_factor: str
    alarm: str


class PanelHeader(StrictModel):
    general: PanelHeaderGeneral
    measures: PanelHeaderMeasures


class PanelDecimalsMeasures(StrictModel):
    voltage: PositiveInt
    current: PositiveInt
    consumption: PositiveInt
    power_factor: PositiveInt


class PanelDecimals(StrictModel):
    general: Dict[str, int]
    measures: PanelDecimalsMeasures


class PayloadConfigPanel(StrictModel):

    send: PanelSend
    save: PanelSave
    header: PanelHeader
    n_decimals: PanelDecimals

    @model_validator(mode="after")
    def validate_send_includes_save(self):
        """Ensure every flag enabled in `save` is also enabled in `send` for both `general` and `measures`."""
        def _check(save_obj, send_obj, base_path):
            for name, val in save_obj.__dict__.items():
                send_val = getattr(send_obj, name, None)
                if isinstance(val, bool):
                    if val and not send_val:
                        raise ValueError(f"In payloads.{base_path}: '{name}' is True in 'save' but False in 'send'.")
        _check(self.save.general, self.send.general, 'panel.save.general')
        _check(self.save.measures, self.send.measures, 'panel.save.measures')
        return self

class PayloadConfigEdge(StrictModel):

    send: EdgeSend
    save: EdgeSave
    header: EdgeHeader
    n_decimals: EdgeDecimals

    @model_validator(mode="after")
    def validate_send_includes_save(self):
        """Ensure every flag enabled in `save` is also enabled in `send` for both `general` and `measures`."""
        def _check(save_obj, send_obj, base_path):
            for name, val in save_obj.__dict__.items():
                send_val = getattr(send_obj, name, None)
                if isinstance(val, bool):
                    if val and not send_val:
                        raise ValueError(f"In payloads.{base_path}: '{name}' is True in 'save' but False in 'send'.")
        _check(self.save.general, self.send.general, 'edge.save.general')
        _check(self.save.measures, self.send.measures, 'edge.save.measures')
        return self

class EdgeGeneralFlags(StrictModel):
    timestamp: bool
    name: bool
    id: bool
    fog_id: bool
    esp_temperature: bool


class EdgeMeasuresFlags(StrictModel):
    voltage: bool
    current: bool
    power_factor: bool
    consumption: bool
   
class EdgeSend(StrictModel):
    transmission_format: Literal["JSON", "CBOR"]
    general: EdgeGeneralFlags
    measures: EdgeMeasuresFlags
    
class EdgeSave(StrictModel):
    storage_format: Literal["SQL", "CSV"]
    general: EdgeGeneralFlags
    measures: EdgeMeasuresFlags

class EdgeHeaderGeneral(StrictModel):
    timestamp: str
    name: str
    id: str
    fog_id: str
    esp_temperature: str


class EdgeHeaderMeasures(StrictModel):
    voltage: str
    current: str
    power_factor: str
    consumption: str


class EdgeHeader(StrictModel):
    general: EdgeHeaderGeneral
    measures: EdgeHeaderMeasures


class EdgeDecimalsMeasures(StrictModel):
    voltage: PositiveInt
    current: PositiveInt
    power_factor: PositiveInt
    consumption: PositiveInt


class EdgeDecimals(StrictModel):
    general: Dict[str, int]
    measures: EdgeDecimalsMeasures

# ----------------------- Report / Costs / Consumption analysis ----------------------- #

class StorageCostsConfig(StrictModel):
    storage_cost_per_GB: NonNegativeFloat
    months_of_storage: PositiveInt


class TransmissionCostsConfig(StrictModel):
    connectivity_cost_per_minute: NonNegativeFloat
    cost_per_mqtt_msg: NonNegativeFloat
    max_KBs_per_message: NonNegativeFloat
    internet_cost_MB_BRL: Dict[str, NonNegativeFloat]


class EstimatedVsSimulatedConfig(StrictModel):
    enable: bool
    yellow_flag_add_price: NonNegativeFloat
    red_flag_1_add_price: NonNegativeFloat
    red_flag_2_add_price: NonNegativeFloat
    estimated_hours_on_per_day: NonNegativeFloat


class ConversionToOtherCurrency(StrictModel):
    enable: bool
    to: str = Field(alias="To")


# ----------------------- Top-level ----------------------- #

class ParametersV2(StrictModel):
    """Root validated configuration model consumed by all runtime modules."""
    debug: bool
    path_json: str = "/app/source/parameters"
    collision: CollisionConfig
    simulation: Simulation
    clustering: ClusteringConfig
    financial: Financial

    @model_validator(mode="after")
    def validate_device_sets(self):
        simulation_devices = set(self.simulation.devices.__dict__.keys())
        financial_devices = set(self.financial.devices.__dict__.keys())
        if simulation_devices != financial_devices:
            raise ValueError(
                "Simulation and Financial device names must match. "
                f"simulation={sorted(simulation_devices)} financial={sorted(financial_devices)}"
            )
        panel_name_field = self.simulation.devices.panel.database.fields.name
        edge_name_field = self.simulation.devices.edge_fog.database.fields.name
        if panel_name_field != edge_name_field:
            raise ValueError(
                "Simulation device 'name' field must match between panel and edge_fog. "
                f"panel={panel_name_field} edge_fog={edge_name_field}"
            )
        return self
