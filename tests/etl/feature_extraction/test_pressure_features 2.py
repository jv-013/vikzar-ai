"""Unit tests for PressureFeatures."""

from __future__ import annotations

import math

import pytest

from app.etl.feature_extraction import PressureFeatures

from .helpers import make_filtered_frame, make_filtered_reading, make_pressure_frame, make_window


def test_computes_load_rate_and_impulse_statistics() -> None:
    frames = [
        make_pressure_frame(0.0, loads=(1.0, 2.0, 3.0)),   # sum 6
        make_pressure_frame(10.0, loads=(2.0, 2.0, 2.0)),  # sum 6
        make_pressure_frame(20.0, loads=(5.0, 5.0, 5.0)),  # sum 15
    ]
    window = make_window(frames)

    result = PressureFeatures().extract(window)
    features = result.features

    assert features["peak_load"] == 15.0
    assert features["mean_load"] == 9.0
    assert features["rms_load"] == math.sqrt(297.0 / 3.0)
    assert features["loading_rate"] == 900.0
    assert features["impulse"] == pytest.approx(0.165)
    assert result.sample_count == 3


def test_empty_window_returns_no_features() -> None:
    window = make_window(frames=[])

    result = PressureFeatures().extract(window)

    assert result.features == {}
    assert result.sample_count == 0


def test_single_frame_returns_only_non_derivative_stats() -> None:
    window = make_window([make_pressure_frame(0.0, loads=(1.0, 2.0, 3.0))])

    result = PressureFeatures().extract(window)

    assert result.features["peak_load"] == 6.0
    assert "loading_rate" not in result.features
    assert "impulse" not in result.features
    assert result.sample_count == 1


def test_missing_fsr_channels_are_skipped_gracefully() -> None:
    frame_with_no_fsr = make_filtered_frame(
        reference_timestamp=0.0,
        readings={"primary_motion": make_filtered_reading(filtered_channels={})},
    )
    frames = [frame_with_no_fsr, make_pressure_frame(10.0, loads=(1.0, 1.0, 1.0))]
    window = make_window(frames)

    result = PressureFeatures().extract(window)

    assert result.features["peak_load"] == 3.0
    assert result.features["mean_load"] == 3.0
    assert result.sample_count == 1


def test_deterministic_and_stateless_across_different_windows() -> None:
    module = PressureFeatures()
    window_a = make_window([make_pressure_frame(0.0, loads=(1.0, 1.0, 1.0))])
    window_b = make_window([make_pressure_frame(0.0, loads=(9.0, 9.0, 9.0))])

    first_a = module.extract(window_a)
    result_b = module.extract(window_b)
    second_a = module.extract(window_a)

    assert first_a == second_a
    assert first_a.features["peak_load"] == 3.0
    assert result_b.features["peak_load"] == 27.0
