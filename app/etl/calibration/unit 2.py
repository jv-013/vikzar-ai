"""
PhysicalUnit: the unit tag attached to every CalibratedChannel value.

See docs/development/CALIBRATION_DESIGN.md.
"""

from __future__ import annotations

from enum import Enum


class PhysicalUnit(str, Enum):
    """
    The physical unit a CalibratedChannel's value is expressed in.

    METERS_PER_SECOND_SQUARED and DEGREES_PER_SECOND are used by
    IMUCalibration; VOLTS is used by EMGCalibration. Their linear
    (scale, offset) form is scientifically well-established for MEMS
    IMUs and ADC-sampled EMG regardless of exact chip, even while the
    numeric coefficients are still development placeholders.

    DEVELOPMENT_PLACEHOLDER is used exclusively by
    FSR402DevelopmentCalibration. Unlike IMU/EMG, the FSR 402's real
    force-response curve is not yet characterized for this hardware —
    not just the coefficients but the shape of the curve itself is
    unknown — so its output must never be tagged with a real force
    unit such as Newtons.
    """

    METERS_PER_SECOND_SQUARED = "m/s^2"
    DEGREES_PER_SECOND = "deg/s"
    VOLTS = "V"
    DEVELOPMENT_PLACEHOLDER = "development_placeholder"
