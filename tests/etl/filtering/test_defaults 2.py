"""Unit tests for default_signal_filter_factories()."""

from __future__ import annotations

from app.etl.filtering.defaults import default_signal_filter_factories
from app.etl.filtering.signal_filter import EMGFilter, FSR402Filter, IMUFilter


def test_covers_every_smart_pod_and_emg_band_channel() -> None:
    factories = default_signal_filter_factories()

    assert set(factories.keys()) == {
        "accel_x", "accel_y", "accel_z",
        "gyro_x", "gyro_y", "gyro_z",
        "fsr_1", "fsr_2", "fsr_3",
        "quadriceps", "hamstring",
    }


def test_each_call_produces_a_fresh_instance_not_shared() -> None:
    """
    The critical departure from Calibration's defaults: unlike
    default_calibration_functions() (which shares one stateless
    instance across a sensor type's axes), each factory call here must
    return a distinct object — SignalFilter instances hold state, so
    sharing would interleave unrelated value histories.
    """
    factories = default_signal_filter_factories()

    first = factories["accel_x"]()
    second = factories["accel_x"]()

    assert first is not second
    assert isinstance(first, IMUFilter)
    assert isinstance(second, IMUFilter)


def test_accelerometer_and_gyroscope_channels_produce_imu_filters() -> None:
    factories = default_signal_filter_factories()

    for channel in ("accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"):
        assert isinstance(factories[channel](), IMUFilter)


def test_fsr_channels_produce_fsr402_filters_regardless_of_position() -> None:
    """Mount-agnostic guarantee: fsr_1/fsr_2/fsr_3 must not be treated
    as different anatomical positions."""
    factories = default_signal_filter_factories()

    for channel in ("fsr_1", "fsr_2", "fsr_3"):
        assert isinstance(factories[channel](), FSR402Filter)


def test_emg_channels_produce_emg_filters() -> None:
    factories = default_signal_filter_factories()

    for channel in ("quadriceps", "hamstring"):
        assert isinstance(factories[channel](), EMGFilter)


def test_returns_a_fresh_dict_on_each_call() -> None:
    first = default_signal_filter_factories()
    second = default_signal_filter_factories()

    assert first is not second
