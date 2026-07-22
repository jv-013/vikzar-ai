"""Unit tests for default_calibration_functions()."""

from __future__ import annotations

from app.etl.calibration.defaults import default_calibration_functions
from app.etl.calibration.function import EMGCalibration, FSR402DevelopmentCalibration, IMUCalibration


def test_covers_every_smart_pod_and_emg_band_channel() -> None:
    functions = default_calibration_functions()

    assert set(functions.keys()) == {
        "accel_x", "accel_y", "accel_z",
        "gyro_x", "gyro_y", "gyro_z",
        "fsr_1", "fsr_2", "fsr_3",
        "quadriceps", "hamstring",
    }


def test_accelerometer_axes_share_one_calibration_instance() -> None:
    functions = default_calibration_functions()

    assert functions["accel_x"] is functions["accel_y"] is functions["accel_z"]
    assert isinstance(functions["accel_x"], IMUCalibration)


def test_gyroscope_axes_share_one_calibration_instance_distinct_from_accelerometer() -> None:
    functions = default_calibration_functions()

    assert functions["gyro_x"] is functions["gyro_y"] is functions["gyro_z"]
    assert functions["gyro_x"] is not functions["accel_x"]


def test_fsr_channels_share_one_calibration_instance_regardless_of_position() -> None:
    """
    Mount-agnostic guarantee (refinement 6): fsr_1/fsr_2/fsr_3 must not
    be treated as different anatomical positions.
    """
    functions = default_calibration_functions()

    assert functions["fsr_1"] is functions["fsr_2"] is functions["fsr_3"]
    assert isinstance(functions["fsr_1"], FSR402DevelopmentCalibration)


def test_emg_channels_share_one_calibration_instance() -> None:
    functions = default_calibration_functions()

    assert functions["quadriceps"] is functions["hamstring"]
    assert isinstance(functions["quadriceps"], EMGCalibration)


def test_returns_a_fresh_dict_on_each_call() -> None:
    first = default_calibration_functions()
    second = default_calibration_functions()

    assert first is not second
    first["accel_x"] = None  # type: ignore[assignment]
    assert second["accel_x"] is not None
