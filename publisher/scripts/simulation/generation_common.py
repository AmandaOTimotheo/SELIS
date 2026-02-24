from datetime import datetime as dt
from typing import Tuple

import numpy as np
import time

from simulation.generator_eletric_states import (
    compute_consumption,
    compute_power_factor,
    generate_current,
    generate_voltage,
)

# common function for building fail masks
def build_fail_masks(rate, size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:

    day_fail_mask = np.random.rand(size) < rate.day_on
    zero_fail_mask = np.random.rand(size) < rate.night_zero_voltage
    low_fail_mask = np.random.rand(size) < rate.night_low_voltage
    transmission_fail_mask = np.random.rand(size) < rate.transmission
    
    return day_fail_mask, zero_fail_mask, low_fail_mask, transmission_fail_mask


# common function for generating measures
def generate_measures(
    p,
    p_device,
    v_cfg,
    c_cfg,
    s_cfg,
    size: int,
    day_fail_mask, zero_fail_mask, low_fail_mask,
    current_dt,
    need_consumption: bool,
    base_voltage=None,
    base_current=None,
    base_power_factor=None,
):

    seed =time.time_ns()
    voltage = generate_voltage(
        seed,
        base_voltage,
        v_cfg.v_upper_variation,
        v_cfg.v_lower_variation,
        zero_fail_mask,
        low_fail_mask,
        size,
    )
    current = generate_current(
        seed,
        base_current,
        c_cfg.c_upper_variation,
        c_cfg.c_lower_variation,
        current_dt.time(),
        p.simulation.daylight.sunrise_start,
        p.simulation.daylight.sunrise_end,
        p.simulation.daylight.sunset_start,
        p.simulation.daylight.sunset_end,
        day_fail_mask,
        zero_fail_mask,
        low_fail_mask,
        size,
    )
    pf = compute_power_factor(
        seed,
        base_power_factor,
        s_cfg.power_factor_variation,
        size,
        current,
    )


    is_day = p.simulation.daylight.sunrise_end <= current_dt.time() <= p.simulation.daylight.sunset_start
    if is_day:
        interval_seconds = p_device.publication_interval_day
    else:
        interval_seconds = p_device.publication_interval_night
    
    consumption = None
    if need_consumption:
        consumption = compute_consumption(voltage, current, pf, interval_seconds)

    return voltage, current, pf, consumption

# common function for formatting timestamp
def format_timestamp(current_dt: dt) -> str:
    return current_dt.strftime("%m-%d-%Y %H:%M:%S")
