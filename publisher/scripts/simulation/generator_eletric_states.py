import numpy as np


def generate_voltage(seed, base, up, low, zero_fail_mask, low_fail_mask, size):
    """Vectorized voltage generation."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(size)
    variations = np.where(z < 0, low * z, up * z)  # assimetria

    voltage = base * (1 + variations)

    # Failures
    voltage[zero_fail_mask] = 0
    voltage[low_fail_mask] *= 0.5

    return voltage


def generate_current(
    seed,
    base,
    up,
    low,
    current_time,
    sunrise_start,
    sunrise_end,
    sunset_start,
    sunset_end,
    day_fail_mask,
    zero_fail_mask,
    low_fail_mask,
    size,
):
    """Vectorized current on-off with sunrise/sunset transitions."""
    # Normal variations (mean=0, std based on provided bounds)
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(size)
    variations = np.where(z < 0, low * z, up * z)  # assimetria

    current_time_sec = (
        current_time.hour * 3600 + current_time.minute * 60 + current_time.second
    )
    sunrise_start_sec = (
        sunrise_start.hour * 3600 + sunrise_start.minute * 60 + sunrise_start.second
    )
    sunrise_end_sec = (
        sunrise_end.hour * 3600 + sunrise_end.minute * 60 + sunrise_end.second
    )
    sunset_start_sec = (
        sunset_start.hour * 3600 + sunset_start.minute * 60 + sunset_start.second
    )
    sunset_end_sec = (
        sunset_end.hour * 3600 + sunset_end.minute * 60 + sunset_end.second
    )

    if current_time >= sunset_end or current_time <= sunrise_start:
        on_mask = np.ones(size, dtype=bool) & (~zero_fail_mask)
    elif sunrise_start < current_time < sunrise_end:
        elapsed_time_sec = current_time_sec - sunrise_start_sec
        total_sunrise_duration_sec = sunrise_end_sec - sunrise_start_sec
        current_factor = 1 - (elapsed_time_sec / total_sunrise_duration_sec)
        on_mask = rng.random(size) < current_factor
        on_mask = on_mask & (~zero_fail_mask)
    elif sunset_start < current_time < sunset_end:
        elapsed_time_sec = current_time_sec - sunset_start_sec
        total_sunset_duration_sec = sunset_end_sec - sunset_start_sec
        current_factor = elapsed_time_sec / total_sunset_duration_sec
        on_mask = rng.random(size) < current_factor
        on_mask = on_mask & (~zero_fail_mask)
    else:
        on_mask = day_fail_mask & (~zero_fail_mask)

    current = np.zeros(size)
    current[on_mask] = base[on_mask] * (1 + variations[on_mask])

    current[low_fail_mask] *= 0.5

    return current


def compute_power_factor(seed, base, variation, size, current):
    # Base power factor
    rng = np.random.default_rng(seed)

    pf = base + variation * rng.standard_normal(size)
    # Failures
    pf[current == 0] = 0
    
    return pf


def compute_consumption(voltage, current, pf, interval_seconds):
    """
    Computes kWh consumption
    """
    return (voltage * current * pf) * (interval_seconds / 3600) / 1000
