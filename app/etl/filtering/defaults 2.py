"""
Default SignalFilter factory registry, assembled from
app.config.etl_config.

See docs/development/FILTERING_DESIGN.md.
"""

from __future__ import annotations

from typing import Callable, Dict

from app.config import etl_config

from .signal_filter import EMGFilter, FSR402Filter, IMUFilter, SignalFilter


def default_signal_filter_factories() -> Dict[str, Callable[[], SignalFilter]]:
    """
    Build the default channel-name -> SignalFilter factory registry.

    Unlike Calibration's default_calibration_functions() (which shares
    one stateless instance across a sensor type's axes, since
    CalibrationFunction has no memory), every entry here is a
    zero-argument callable that produces a FRESH instance on every
    call. SignalFilter instances hold per-stream state (filter
    history) — sharing one instance across accel_x/accel_y/accel_z, or
    across synchronization groups, would silently interleave unrelated
    value histories. Filterer relies on this: it calls each factory
    once per (group_id, channel_name) pair it encounters, caching the
    resulting instance for that pair only.

    Returns:
        A new dict mapping each known channel name to its factory. A
        fresh dict is returned on every call; callers that construct a
        Filterer own their own copy.
    """
    return {
        "accel_x": lambda: IMUFilter(alpha=etl_config.DEV_ACCEL_FILTER_ALPHA),
        "accel_y": lambda: IMUFilter(alpha=etl_config.DEV_ACCEL_FILTER_ALPHA),
        "accel_z": lambda: IMUFilter(alpha=etl_config.DEV_ACCEL_FILTER_ALPHA),
        "gyro_x": lambda: IMUFilter(alpha=etl_config.DEV_GYRO_FILTER_ALPHA),
        "gyro_y": lambda: IMUFilter(alpha=etl_config.DEV_GYRO_FILTER_ALPHA),
        "gyro_z": lambda: IMUFilter(alpha=etl_config.DEV_GYRO_FILTER_ALPHA),
        "fsr_1": lambda: FSR402Filter(alpha=etl_config.DEV_FSR402_FILTER_ALPHA),
        "fsr_2": lambda: FSR402Filter(alpha=etl_config.DEV_FSR402_FILTER_ALPHA),
        "fsr_3": lambda: FSR402Filter(alpha=etl_config.DEV_FSR402_FILTER_ALPHA),
        "quadriceps": lambda: EMGFilter(alpha=etl_config.DEV_EMG_FILTER_ALPHA),
        "hamstring": lambda: EMGFilter(alpha=etl_config.DEV_EMG_FILTER_ALPHA),
    }
