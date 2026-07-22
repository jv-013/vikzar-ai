"""Unit tests for the RawFeatureVector validation trust boundary."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest

from app.schemas.raw_feature_vector import RawFeatureVector
from app.validation import (
    FeatureValidationError,
    RawFeatureVectorValidator,
    SchemaValidationError,
    ValidatedRawFeatureVector,
    validate_raw_feature_vector,
)


def _valid_payload() -> dict[str, Any]:
    """Return one valid, lossless RawFeatureVector payload."""

    return {
        "feature_vector_id": "rfv-001",
        "timestamp": datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
        "schema_version": "1.0.0",
        "source": "vikzar_etl_v1",
        "player": {
            "player_id": "player-001",
            "age": 24,
            "sex": "male",
            "dominant_leg": "right",
            "position": "forward",
        },
        "session": {"session_id": "session-001"},
        "hardware": {
            "firmware_revision": "fw-1.0.0",
            "hardware_revision": "hw-v1",
            "protocol_version": "1",
        },
        "groups": {
            "left_lower_limb": {
                "window_start": 0.0,
                "window_end": 1000.0,
                "motion": {
                    "biomarkers": {"peak_resultant_acceleration": 5.0},
                    "quality": {
                        "peak_resultant_acceleration": {
                            "status": "valid",
                            "flags": [],
                            "rationale": "ETL feature validation accepted the value.",
                        }
                    },
                },
            }
        },
    }


def test_validate_raw_feature_vector_returns_existing_instance() -> None:
    """Validation marks a parsed ETL payload trusted without replacing it."""

    raw_feature_vector = RawFeatureVector(**_valid_payload())

    validated = validate_raw_feature_vector(raw_feature_vector)

    assert validated is raw_feature_vector
    assert isinstance(validated, ValidatedRawFeatureVector)


def test_validate_raw_feature_vector_parses_mapping_input() -> None:
    """Mapping input is parsed through the locked RawFeatureVector schema."""

    validated = validate_raw_feature_vector(_valid_payload())

    assert isinstance(validated, RawFeatureVector)
    assert validated.feature_vector_id == "rfv-001"


def test_validate_raises_schema_error_for_missing_required_field() -> None:
    """Missing RawFeatureVector fields fail before semantic validation."""

    payload = deepcopy(_valid_payload())
    del payload["player"]["player_id"]

    with pytest.raises(SchemaValidationError):
        validate_raw_feature_vector(payload)


def test_validate_raises_schema_error_for_unsupported_input_type() -> None:
    """Only RawFeatureVector instances and mappings enter the boundary."""

    with pytest.raises(SchemaValidationError):
        validate_raw_feature_vector(object())  # type: ignore[arg-type]


def test_validate_reports_blank_identity_field() -> None:
    """Identity metadata required for downstream AI cannot be blank."""

    payload = deepcopy(_valid_payload())
    payload["feature_vector_id"] = " "

    report = RawFeatureVectorValidator().validate(payload)

    assert not report.is_valid
    assert "VAL_EMPTY_IDENTITY_FIELD" in {issue.code for issue in report.errors}


def test_validate_or_raise_rejects_semantic_identity_error() -> None:
    """The trust boundary raises when semantic validation fails."""

    payload = deepcopy(_valid_payload())
    payload["source"] = ""

    with pytest.raises(FeatureValidationError) as exc_info:
        validate_raw_feature_vector(payload)

    assert exc_info.value.report is not None
    assert exc_info.value.report.error_count == 1


def test_rejected_non_finite_biomarker_remains_losslessly_available() -> None:
    """AI receives ETL quality metadata instead of a fabricated replacement value."""

    payload = deepcopy(_valid_payload())
    motion = payload["groups"]["left_lower_limb"]["motion"]
    motion["biomarkers"]["peak_resultant_acceleration"] = float("nan")
    motion["quality"]["peak_resultant_acceleration"] = {
        "status": "rejected",
        "flags": ["non_finite_value"],
        "rationale": "ETL retained the rejected value with its quality annotation.",
    }

    report = RawFeatureVectorValidator().validate(payload)

    assert report.is_valid
