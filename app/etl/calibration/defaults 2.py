"""
Default CalibrationFunction registry, assembled from app.config.etl_config.

See docs/development/CALIBRATION_DESIGN.md.
"""

from __future__ import annotations

from typing import Dict

from app.config import etl_config

from .function import CalibrationFunction, EMGCalibration, FSR402DevelopmentCalibration, IMUCalibration
from .unit import PhysicalUnit


def default_calibration_functions() -> Dict[str, CalibrationFunction]:
    """
    Build the default channel-name -> CalibrationFunction registry.

    Each sensor type gets exactly one CalibrationFunction instance,
    shared across all of its channels (all three accelerometer axes
    share one IMUCalibration instance, all three FSR channels share one
    FSR402DevelopmentCalibration instance, and so on) — those channels
    come from identical physical sensor units with no scientific reason
    to differ, and treating fsr_1/fsr_2/fsr_3 identically is itself part
    of preserving the Smart Pod's mount-agnostic design (they must not
    be assumed to represent different anatomical positions).

    Returns:
        A new dict mapping each known channel name to its
        CalibrationFunction. A fresh dict is returned on every call;
        callers that construct a Calibrator own their own copy.
    """
    accel = IMUCalibration(
        scale=etl_config.DEV_ACCEL_SCALE,
        offset=etl_config.DEV_ACCEL_OFFSET,
        unit=PhysicalUnit.METERS_PER_SECOND_SQUARED,
    )
    gyro = IMUCalibration(
        scale=etl_config.DEV_GYRO_SCALE,
        offset=etl_config.DEV_GYRO_OFFSET,
        unit=PhysicalUnit.DEGREES_PER_SECOND,
    )
    emg = EMGCalibration(
        scale=etl_config.DEV_EMG_SCALE,
        offset=etl_config.DEV_EMG_OFFSET,
        unit=PhysicalUnit.VOLTS,
    )
    fsr = FSR402DevelopmentCalibration(
        scale=etl_config.DEV_FSR402_SCALE,
        offset=etl_config.DEV_FSR402_OFFSET,
    )

    return {
        "accel_x": accel,
        "accel_y": accel,
        "accel_z": accel,
        "gyro_x": gyro,
        "gyro_y": gyro,
        "gyro_z": gyro,
        "fsr_1": fsr,
        "fsr_2": fsr,
        "fsr_3": fsr,
        "quadriceps": emg,
        "hamstring": emg,
    }
