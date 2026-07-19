"""Unit tests for the FeatureVector validator."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

import pytest

from app.schemas.feature_vector import FeatureVector
from app.validation import (
    FeatureValidationError,
    FeatureVectorValidator,
    SchemaValidationError,
    validate_feature_vector,
)


def _valid_payload() -> dict[str, Any]:
    """Return a valid FeatureVector payload for validator tests."""

    timestamp = datetime(2026, 7, 16, 12, 0, 0)
    return {
        "metadata": {
            "feature_vector_id": "fv-001",
            "timestamp": timestamp,
            "schema_version": "1.0.0",
            "window_start": timestamp - timedelta(milliseconds=50),
            "window_end": timestamp + timedelta(milliseconds=50),
            "sampling_rate_hz": 100,
            "window_size_ms": 100,
            "window_overlap_percent": 0,
        },
        "player": {
            "player_id": "player-001",
            "age": 24,
            "sex": "male",
            "height_cm": 180.0,
            "weight_kg": 75.0,
            "bmi": 23.1,
            "dominant_leg": "right",
            "position": "forward",
            "fitness_level": "professional",
            "injury_history": None,
            "injury_status": None,
        },
        "session": {
            "session_id": "session-001",
            "drill": "sprint",
            "training_intensity": "high",
            "surface": "grass",
            "footwear": "boots",
            "weather": "clear",
            "temperature_c": 28.0,
            "humidity_percent": 60.0,
            "fatigue_level": 20.0,
        },
        "imu": {
            "mean_acceleration": 2.0,
            "peak_acceleration": 5.5,
            "min_acceleration": -1.0,
            "resultant_acceleration": 3.5,
            "rms_acceleration": 2.2,
            "acceleration_variance": 0.3,
            "acceleration_std": 0.5,
            "mean_jerk": 0.2,
            "peak_jerk": 1.1,
            "mean_angular_velocity": 0.8,
            "peak_angular_velocity": 2.4,
            "angular_velocity_variance": 0.2,
            "rotation_magnitude": 1.4,
            "estimated_cadence": 170.0,
            "estimated_stride_frequency": 2.8,
        },
        "fsr": {
            "mean_load": 20.0,
            "peak_load": 40.0,
            "min_load": 10.0,
            "total_impulse": 120.0,
            "ground_contact_time": 0.22,
            "loading_rate": 4.0,
            "unloading_rate": 3.5,
            "heel_load_percentage": 20.0,
            "midfoot_load_percentage": 30.0,
            "forefoot_load_percentage": 50.0,
            "left_right_loading_symmetry": 92.0,
        },
        "emg": {
            "mean_activation": 35.0,
            "peak_activation": 80.0,
            "rms_activation": 45.0,
            "activation_duration": 0.4,
            "fatigue_index": 18.0,
            "activation_variability": 4.0,
            "left_quadriceps_mean": 40.0,
            "right_quadriceps_mean": 42.0,
            "left_hamstring_mean": 30.0,
            "right_hamstring_mean": 31.0,
            "left_right_asymmetry": 4.0,
            "hamstring_quadriceps_ratio": 0.75,
            "co_activation_index": 0.2,
            "activation_onset_timing": 0.1,
        },
        "muscles": {
            "left_quadriceps_activation": 60.0,
            "right_quadriceps_activation": 62.0,
            "left_hamstring_activation": 44.0,
            "right_hamstring_activation": 45.0,
            "hamstring_quadriceps_ratio": 0.72,
            "left_right_activation_asymmetry": 3.0,
            "estimated_muscle_fatigue": 25.0,
            "confidence_score": 0.93,
        },
        "derived": {
            "cadence": 170.0,
            "stride_frequency": 2.8,
            "stride_length": 1.4,
            "movement_intensity": 70.0,
            "braking_force": 12.0,
            "propulsion_force": 15.0,
            "vertical_oscillation": 6.0,
            "stance_time": 0.18,
            "swing_time": 0.22,
            "flight_time": 0.05,
            "change_of_direction_angle": 35.0,
            "turning_rate": 2.0,
            "landing_stability": 85.0,
            "landing_force_distribution": 80.0,
            "gait_stability": 88.0,
            "movement_efficiency": 82.0,
            "cumulative_mechanical_load": 350.0,
        },
        "symmetry": {
            "quadriceps_symmetry": 94.0,
            "hamstring_symmetry": 95.0,
            "loading_symmetry": 92.0,
            "stride_symmetry": 96.0,
            "stance_time_symmetry": 94.0,
            "swing_time_symmetry": 95.0,
            "overall_symmetry_score": 94.0,
        },
        "context": {},
        "labels": {},
        "system": {
            "validation_status": True,
            "quality_score": 96.0,
            "processing_time_ms": 12.0,
            "source": "etl",
        },
    }


def test_validate_feature_vector_returns_existing_instance() -> None:
    """FeatureVector input is validated without being replaced or mutated."""

    feature_vector = FeatureVector(**_valid_payload())

    validated = validate_feature_vector(feature_vector)

    assert validated is feature_vector


def test_validate_feature_vector_parses_mapping_input() -> None:
    """Mapping input is parsed through Pydantic and returned as FeatureVector."""

    validated = validate_feature_vector(_valid_payload())

    assert isinstance(validated, FeatureVector)
    assert validated.metadata.feature_vector_id == "fv-001"


def test_validate_raises_schema_error_for_missing_required_field() -> None:
    """Missing schema-required fields fail before semantic validation."""

    payload = deepcopy(_valid_payload())
    del payload["player"]["player_id"]

    with pytest.raises(SchemaValidationError):
        validate_feature_vector(payload)


def test_validate_raises_schema_error_for_unsupported_input_type() -> None:
    """Unsupported input types are rejected with a schema validation error."""

    with pytest.raises(SchemaValidationError):
        validate_feature_vector(object())  # type: ignore[arg-type]


def test_validate_reports_timestamp_outside_window() -> None:
    """Timestamp/window inconsistencies are reported as semantic errors."""

    payload = deepcopy(_valid_payload())
    payload["metadata"]["timestamp"] = (
        payload["metadata"]["window_end"] + timedelta(seconds=1)
    )

    report = FeatureVectorValidator().validate(payload)

    assert not report.is_valid
    assert "VAL_TIMESTAMP_OUTSIDE_WINDOW" in {
        issue.code for issue in report.errors
    }


def test_validate_or_raise_raises_for_semantic_error() -> None:
    """Semantic validation failures raise FeatureValidationError on demand."""

    payload = deepcopy(_valid_payload())
    payload["system"]["validation_status"] = False

    with pytest.raises(FeatureValidationError) as exc_info:
        validate_feature_vector(payload)

    assert exc_info.value.report is not None
    assert exc_info.value.report.error_count == 1


def test_validate_reports_non_finite_numeric_value() -> None:
    """NaN and infinite numeric values are rejected by semantic validation."""

    payload = deepcopy(_valid_payload())
    payload["imu"]["min_acceleration"] = float("nan")

    report = FeatureVectorValidator().validate(payload)

    assert not report.is_valid
    assert "VAL_NON_FINITE_NUMBER" in {issue.code for issue in report.errors}
