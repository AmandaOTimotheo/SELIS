import pytz
from datetime import datetime as dt, timedelta

def load_time(p, device_key: str):
    """
    Returns:
    --------
    current_dt: datetime localized
    stop_dt: datetime localized
    """
    w = p.simulation.window
    tz = pytz.timezone(w.time_zone)

    # Start datetime
    if w.use_current_time_and_date:
        current_dt = dt.now(tz)
    else:
        current_dt = tz.localize(
            dt.combine(w.simulation_start_date, w.simulation_start_time)
        )

    # Stop datetime
    device = getattr(p.simulation.devices, device_key, None)

    simulation_enabled = device.modes.offline_simulation.enable

    if simulation_enabled:
        stop_dt = tz.localize(
            dt.combine(w.simulation_stop_date, w.simulation_stop_time)
        )
    else:
        # Infinite stop
        stop_dt = tz.localize(dt(9000, 1, 1))

    # check if current_dt is before stop_dt
    if current_dt >= stop_dt:
        raise ValueError(
            f"Simulation start time {current_dt} must be before stop time {stop_dt}."
        )
    
    return current_dt, stop_dt


def load_suntime(p):
    """Returns (sunrise_start, sunrise_end, sunset_start, sunset_end)"""

    d = p.simulation.daylight

    return (
        d.sunrise_start,
        d.sunrise_end,
        d.sunset_start,
        d.sunset_end
    )



def get_interval(p, device_key: str, current_dt: dt, count_iterations: int):
    """
    Unified time-control for PANEL and FOG/EDGE devices.
    Supports:
    - Real-time mode
    - Simulation mode
    - Automatic day/night interval selection
    """

    sunrise_end = p.simulation.daylight.sunrise_end
    sunset_start = p.simulation.daylight.sunset_start

    tz = pytz.timezone(p.simulation.window.time_zone)

    device = getattr(p.simulation.devices, device_key, None)

    mode = device.modes
    interval_day = device.publication_interval_day
    interval_night = device.publication_interval_night

    def get_interval_for_time(active_dt, advance_time):
        if sunrise_end <= active_dt.time() <= sunset_start:
            interval = interval_day
        else:
            interval = interval_night

        if advance_time and count_iterations > 1:
            active_dt = active_dt + timedelta(seconds=interval)

        return interval, active_dt
    # -----------------------------
    # REAL-TIME MODE
    # -----------------------------
    if mode.real_time_simulation.enable:
        if p.simulation.window.use_current_time_and_date:
            now = dt.now(tz)
            return get_interval_for_time(now, False)
        return get_interval_for_time(current_dt, True)

    # -----------------------------
    # SIMULATION MODE
    # -----------------------------
    if mode.offline_simulation.enable:
        return get_interval_for_time(current_dt, True)

    raise RuntimeError("Neither real-time nor simulation mode is enabled.")
