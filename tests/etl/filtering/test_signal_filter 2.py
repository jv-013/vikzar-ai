"""
Unit tests for SignalFilter implementations.

Uses deliberately non-trivial (non-identity) alpha values, distinct from
etl_config's provisional 1.0 defaults, so these tests exercise the real
EMA arithmetic rather than trivially passing under a passthrough that
could mask a bug where smoothing is never applied.
"""

from __future__ import annotations

import pytest

from app.etl.filtering.signal_filter import EMGFilter, FSR402Filter, IMUFilter, _ExponentialMovingAverage


def test_first_sample_is_returned_unchanged_bootstrap() -> None:
    ema = _ExponentialMovingAverage(alpha=0.3)

    assert ema.apply(42.0) == 42.0


def test_second_sample_blends_with_first_per_ema_formula() -> None:
    ema = _ExponentialMovingAverage(alpha=0.5)

    first = ema.apply(10.0)
    second = ema.apply(20.0)

    assert first == 10.0
    assert second == 0.5 * 20.0 + 0.5 * 10.0


def test_third_sample_blends_with_running_output_not_raw_history() -> None:
    ema = _ExponentialMovingAverage(alpha=0.5)

    ema.apply(10.0)
    ema.apply(20.0)
    third = ema.apply(30.0)

    assert third == 0.5 * 30.0 + 0.5 * 15.0


def test_alpha_of_one_is_a_pure_passthrough() -> None:
    ema = _ExponentialMovingAverage(alpha=1.0)

    assert ema.apply(5.0) == 5.0
    assert ema.apply(999.0) == 999.0


@pytest.mark.parametrize("bad_alpha", [0.0, -0.1, 1.1, 2.0])
def test_rejects_alpha_out_of_range(bad_alpha: float) -> None:
    with pytest.raises(ValueError):
        _ExponentialMovingAverage(alpha=bad_alpha)


def test_imu_filter_smooths_using_ema() -> None:
    signal_filter = IMUFilter(alpha=0.5)

    first = signal_filter.filter(10.0)
    second = signal_filter.filter(20.0)

    assert first == 10.0
    assert second == 15.0


def test_emg_filter_smooths_using_ema() -> None:
    signal_filter = EMGFilter(alpha=0.5)

    first = signal_filter.filter(10.0)
    second = signal_filter.filter(20.0)

    assert first == 10.0
    assert second == 15.0


def test_fsr402_filter_smooths_using_ema() -> None:
    signal_filter = FSR402Filter(alpha=0.5)

    first = signal_filter.filter(10.0)
    second = signal_filter.filter(20.0)

    assert first == 10.0
    assert second == 15.0


def test_two_imu_filter_instances_have_independent_state() -> None:
    a = IMUFilter(alpha=0.5)
    b = IMUFilter(alpha=0.5)

    a.filter(100.0)
    a.filter(100.0)

    assert b.filter(0.0) == 0.0
