"""Unit tests for individual validation rules."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from app.schemas.feature_vector import FeatureVector
from app.validation.rules import (
    IdentityFieldsRule,
    InternalConsistencyRule,
    MetadataTimeWindowRule,
)
from test_validator import _valid_payload


def test_identity_fields_rule_rejects_blank_player_id() -> None:
    """IdentityFieldsRule rejects blank identity strings."""

    payload = deepcopy(_valid_payload())
    payload["player"]["player_id"] = "  "
    feature_vector = FeatureVector(**payload)

    issues = IdentityFieldsRule().validate(feature_vector)

    assert len(issues) == 1
    assert issues[0].code == "VAL_EMPTY_IDENTITY_FIELD"
    assert issues[0].field_path == "player.player_id"


def test_metadata_time_window_rule_rejects_invalid_window_order() -> None:
    """MetadataTimeWindowRule rejects windows that do not move forward."""

    payload = deepcopy(_valid_payload())
    payload["metadata"]["window_start"] = payload["metadata"]["window_end"]
    feature_vector = FeatureVector(**payload)

    issues = MetadataTimeWindowRule().validate(feature_vector)

    assert "VAL_INVALID_TIME_WINDOW" in {issue.code for issue in issues}


def test_metadata_time_window_rule_rejects_timestamp_outside_window() -> None:
    """MetadataTimeWindowRule rejects timestamps outside their feature window."""

    payload = deepcopy(_valid_payload())
    payload["metadata"]["timestamp"] = (
        payload["metadata"]["window_end"] + timedelta(milliseconds=1)
    )
    feature_vector = FeatureVector(**payload)

    issues = MetadataTimeWindowRule().validate(feature_vector)

    assert "VAL_TIMESTAMP_OUTSIDE_WINDOW" in {issue.code for issue in issues}


def test_internal_consistency_rule_rejects_load_order_violation() -> None:
    """InternalConsistencyRule rejects impossible FSR load ordering."""

    payload = deepcopy(_valid_payload())
    payload["fsr"]["mean_load"] = 50.0
    feature_vector = FeatureVector(**payload)

    issues = InternalConsistencyRule().validate(feature_vector)

    assert "VAL_INCONSISTENT_FSR_LOAD" in {issue.code for issue in issues}
