"""Unit tests for MuscleFeatures."""

from __future__ import annotations

import math

from app.etl.feature_extraction import MuscleFeatures

from .helpers import make_emg_frame, make_window


def test_computes_rms_and_mav_per_muscle() -> None:
    frames = [
        make_emg_frame(0.0, quadriceps=3.0, hamstring=1.0),
        make_emg_frame(10.0, quadriceps=4.0, hamstring=2.0),
        make_emg_frame(20.0, quadriceps=5.0, hamstring=3.0),
    ]
    window = make_window(frames)

    result = MuscleFeatures().extract(window)
    features = result.features

    assert features["quadriceps_rms"] == math.sqrt(50.0 / 3.0)
    assert features["quadriceps_mean_absolute_value"] == 4.0
    assert features["hamstring_rms"] == math.sqrt(14.0 / 3.0)
    assert features["hamstring_mean_absolute_value"] == 2.0
    assert result.sample_count == 3


def test_no_emg_role_anywhere_returns_empty_not_fabricated() -> None:
    frames = [make_emg_frame(0.0), make_emg_frame(10.0)]  # no quadriceps/hamstring given
    window = make_window(frames)

    result = MuscleFeatures().extract(window)

    assert result.features == {}
    assert result.sample_count == 0


def test_empty_window_returns_no_features() -> None:
    window = make_window(frames=[])

    result = MuscleFeatures().extract(window)

    assert result.features == {}
    assert result.sample_count == 0


def test_only_one_muscle_channel_present_computes_only_that_muscle() -> None:
    frames = [make_emg_frame(0.0, quadriceps=10.0)]
    window = make_window(frames)

    result = MuscleFeatures().extract(window)

    assert "quadriceps_rms" in result.features
    assert "hamstring_rms" not in result.features
    assert result.sample_count == 1


def test_partial_emg_frames_use_only_frames_that_have_data() -> None:
    frames = [
        make_emg_frame(0.0, quadriceps=10.0),
        make_emg_frame(10.0),  # this frame has no emg reading at all
        make_emg_frame(20.0, quadriceps=20.0),
    ]
    window = make_window(frames)

    result = MuscleFeatures().extract(window)

    assert result.features["quadriceps_mean_absolute_value"] == 15.0
    # sample_count reflects frames with an emg reading present (2),
    # not window length (3) and not per-channel presence.
    assert result.sample_count == 2


def test_deterministic_and_stateless_across_different_windows() -> None:
    module = MuscleFeatures()
    window_a = make_window([make_emg_frame(0.0, quadriceps=1.0)])
    window_b = make_window([make_emg_frame(0.0, quadriceps=9.0)])

    first_a = module.extract(window_a)
    result_b = module.extract(window_b)
    second_a = module.extract(window_a)

    assert first_a == second_a
    assert first_a.features["quadriceps_rms"] == 1.0
    assert result_b.features["quadriceps_rms"] == 9.0
