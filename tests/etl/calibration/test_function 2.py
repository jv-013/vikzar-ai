"""
Unit tests for CalibrationFunction implementations.

Uses deliberately non-trivial (non-identity) scale/offset values, distinct
from etl_config's provisional 1.0/0.0 defaults, so these tests exercise
the real arithmetic rather than trivially passing under an identity
transform that could mask a bug where scale/offset are never applied.
"""

from __future__ import annotations

from app.etl.calibration.function import EMGCalibration, FSR402DevelopmentCalibration, IMUCalibration
from app.etl.calibration.unit import PhysicalUnit


def test_imu_calibration_applies_scale_and_offset() -> None:
    calibration = IMUCalibration(scale=0.5, offset=10.0, unit=PhysicalUnit.METERS_PER_SECOND_SQUARED)

    result = calibration.calibrate(100)

    assert result.value == 100 * 0.5 - 10.0
    assert result.unit == PhysicalUnit.METERS_PER_SECOND_SQUARED


def test_imu_calibration_handles_negative_raw_values() -> None:
    calibration = IMUCalibration(scale=2.0, offset=5.0, unit=PhysicalUnit.DEGREES_PER_SECOND)

    result = calibration.calibrate(-30)

    assert result.value == -30 * 2.0 - 5.0
    assert result.unit == PhysicalUnit.DEGREES_PER_SECOND


def test_emg_calibration_applies_scale_and_offset() -> None:
    calibration = EMGCalibration(scale=3.3 / 4095, offset=0.1, unit=PhysicalUnit.VOLTS)

    result = calibration.calibrate(2048)

    assert result.value == 2048 * (3.3 / 4095) - 0.1
    assert result.unit == PhysicalUnit.VOLTS


def test_fsr402_development_calibration_applies_scale_and_offset() -> None:
    calibration = FSR402DevelopmentCalibration(scale=0.01, offset=1.0)

    result = calibration.calibrate(500)

    assert result.value == 500 * 0.01 - 1.0


def test_fsr402_development_calibration_never_claims_a_real_force_unit() -> None:
    calibration = FSR402DevelopmentCalibration(scale=1.0, offset=0.0)

    result = calibration.calibrate(500)

    assert result.unit == PhysicalUnit.DEVELOPMENT_PLACEHOLDER


def test_calibration_functions_are_deterministic() -> None:
    calibration = IMUCalibration(scale=0.5, offset=10.0, unit=PhysicalUnit.METERS_PER_SECOND_SQUARED)

    first = calibration.calibrate(100)
    second = calibration.calibrate(100)

    assert first == second
