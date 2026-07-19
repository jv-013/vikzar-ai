"""Unit tests for RawFeatureVector semantic validation rules."""

from __future__ import annotations

from copy import deepcopy

from app.schemas.raw_feature_vector import RawFeatureVector
from app.validation.rules import (
    GroupWindowRule,
    IdentityFieldsRule,
    QualityAnnotationRule,
)
from test_validator import _valid_payload


def test_identity_fields_rule_rejects_blank_player_id() -> None:
    """IdentityFieldsRule rejects blank RawFeatureVector identity strings."""

    payload = deepcopy(_valid_payload())
    payload["player"]["player_id"] = "  "

    issues = IdentityFieldsRule().validate(RawFeatureVector(**payload))

    assert len(issues) == 1
    assert issues[0].code == "VAL_EMPTY_IDENTITY_FIELD"
    assert issues[0].field_path == "player.player_id"


def test_group_window_rule_rejects_invalid_window_order() -> None:
    """GroupWindowRule guards model-constructed input at the trust boundary."""

    raw_feature_vector = RawFeatureVector(**_valid_payload())
    raw_feature_vector.groups["left_lower_limb"].window_end = 0.0

    issues = GroupWindowRule().validate(raw_feature_vector)

    assert "VAL_INVALID_GROUP_TIME_WINDOW" in {issue.code for issue in issues}


def test_quality_annotation_rule_rejects_mismatched_keys() -> None:
    """Every carried ETL biomarker must retain one matching quality record."""

    raw_feature_vector = RawFeatureVector(**_valid_payload())
    domain = raw_feature_vector.groups["left_lower_limb"].motion
    assert domain is not None
    domain.quality.clear()

    issues = QualityAnnotationRule().validate(raw_feature_vector)

    assert "VAL_QUALITY_KEY_MISMATCH" in {issue.code for issue in issues}
