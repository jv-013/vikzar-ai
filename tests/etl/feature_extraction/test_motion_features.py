"""Unit tests for MotionFeatures."""

from __future__ import annotations

import math

from app.etl.feature_extraction import MotionFeatures

from .helpers import make_motion_frame, make_window


def test_computes_acceleration_and_jerk_statistics() -> None:
    frames = [
        make_motion_frame(0.0, accel=(3.0, 4.0, 0.0)),   # resultant 5
        make_motion_frame(10.0, accel=(0.0, 0.0, 0.0)),  # resultant 0
        make_motion_frame(20.0, accel=(6.0, 8.0, 0.0)),  # resultant 10
    ]
    window = make_window(frames)

    result = MotionFeatures().extract(window)
    features = result.features

    assert features["peak_resultant_acceleration"] == 10.0
    assert features["mean_resultant_acceleration"] == 5.0
    assert features["rms_resultant_acceleration"] == math.sqrt(125.0 / 3.0)
    assert features["mean_jerk"] == 750.0
    assert features["peak_jerk"] == 1000.0
    # middle sample (0) is a local minimum, not a maximum: 0 peaks
    assert features["cadence_per_minute"] == 0.0
    assert result.sample_count == 3


def test_computes_cadence_from_local_maxima() -> None:
    frames = [
        make_motion_frame(0.0, accel=(0.0, 0.0, 0.0)),
        make_motion_frame(10.0, accel=(5.0, 0.0, 0.0)),
        make_motion_frame(20.0, accel=(0.0, 0.0, 0.0)),
        make_motion_frame(30.0, accel=(5.0, 0.0, 0.0)),
        make_motion_frame(40.0, accel=(0.0, 0.0, 0.0)),
    ]
    window = make_window(frames, window_start=0.0, window_end=1000.0)

    features = MotionFeatures().extract(window).features

    # 2 local maxima over a 1-second (1/60 minute) window
    assert features["cadence_per_minute"] == 2.0 / (1.0 / 60.0)


def test_peak_angular_velocity() -> None:
    frames = [
        make_motion_frame(0.0, gyro=(3.0, 4.0, 0.0)),   # resultant 5
        make_motion_frame(10.0, gyro=(0.0, 0.0, 12.0)),  # resultant 12
    ]
    window = make_window(frames)

    features = MotionFeatures().extract(window).features

    assert features["peak_angular_velocity"] == 12.0


def test_empty_window_returns_no_features() -> None:
    window = make_window(frames=[])

    result = MotionFeatures().extract(window)

    assert result.features == {}
    assert result.sample_count == 0


def test_single_frame_returns_only_non_derivative_stats() -> None:
    window = make_window([make_motion_frame(0.0, accel=(3.0, 4.0, 0.0))])

    result = MotionFeatures().extract(window)
    features = result.features

    assert features["peak_resultant_acceleration"] == 5.0
    assert "mean_jerk" not in features
    assert "peak_jerk" not in features
    assert "cadence_per_minute" not in features
    assert result.sample_count == 1


def test_two_frames_computes_jerk_but_not_cadence() -> None:
    frames = [
        make_motion_frame(0.0, accel=(3.0, 4.0, 0.0)),
        make_motion_frame(10.0, accel=(0.0, 0.0, 0.0)),
    ]
    window = make_window(frames)

    result = MotionFeatures().extract(window)

    assert "mean_jerk" in result.features
    assert "cadence_per_minute" not in result.features
    assert result.sample_count == 2


def test_missing_accel_channels_are_skipped_gracefully() -> None:
    frames = [
        make_motion_frame(0.0, accel=None, gyro=(1.0, 0.0, 0.0)),
        make_motion_frame(10.0, accel=(3.0, 4.0, 0.0), gyro=None),
    ]
    window = make_window(frames)

    result = MotionFeatures().extract(window)

    assert result.features["peak_resultant_acceleration"] == 5.0
    assert result.features["peak_angular_velocity"] == 1.0
    # only 1 of the 2 frames had a full accel triple
    assert result.sample_count == 1


def test_deterministic_and_stateless_across_different_windows() -> None:
    module = MotionFeatures()
    window_a = make_window([make_motion_frame(0.0, accel=(3.0, 4.0, 0.0))])
    window_b = make_window([make_motion_frame(0.0, accel=(0.0, 0.0, 5.0))])

    first_a = module.extract(window_a)
    result_b = module.extract(window_b)
    second_a = module.extract(window_a)

    assert first_a == second_a
    assert first_a.features["peak_resultant_acceleration"] == 5.0
    assert result_b.features["peak_resultant_acceleration"] == 5.0
