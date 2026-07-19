"""Semantic validation rules for the locked RawFeatureVector contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.raw_feature_vector import RawFeatureVector
from app.validation.report import ValidationIssue


class RawFeatureVectorRule(ABC):
    """Base class for one semantic RawFeatureVector validation rule."""

    name: str

    @abstractmethod
    def validate(self, raw_feature_vector: RawFeatureVector) -> list[ValidationIssue]:
        """Return semantic validation issues for one parsed RawFeatureVector."""


class RequiredSectionsRule(RawFeatureVectorRule):
    """Validate required top-level RawFeatureVector sections."""

    name = "required_sections"
    _sections = (
        "feature_vector_id",
        "timestamp",
        "schema_version",
        "source",
        "player",
        "session",
        "hardware",
        "groups",
    )

    def validate(self, raw_feature_vector: RawFeatureVector) -> list[ValidationIssue]:
        """Return errors for absent or null contract sections."""

        return [
            ValidationIssue(
                code="VAL_REQUIRED_SECTION",
                field_path=section,
                message=f"RawFeatureVector section '{section}' is required.",
            )
            for section in self._sections
            if getattr(raw_feature_vector, section, None) is None
        ]


class IdentityFieldsRule(RawFeatureVectorRule):
    """Validate non-empty identifiers and provenance strings."""

    name = "identity_fields"
    _field_paths = (
        "feature_vector_id",
        "schema_version",
        "source",
        "player.player_id",
        "player.sex",
        "player.dominant_leg",
        "player.position",
        "session.session_id",
        "hardware.firmware_revision",
        "hardware.hardware_revision",
        "hardware.protocol_version",
    )

    def validate(self, raw_feature_vector: RawFeatureVector) -> list[ValidationIssue]:
        """Return errors for blank identity and provenance fields."""

        issues: list[ValidationIssue] = []
        for field_path in self._field_paths:
            value = _get_nested_value(raw_feature_vector, field_path)
            if not isinstance(value, str) or not value.strip():
                issues.append(
                    ValidationIssue(
                        code="VAL_EMPTY_IDENTITY_FIELD",
                        field_path=field_path,
                        message=f"Field '{field_path}' must be a non-empty string.",
                    )
                )
        return issues


class GroupWindowRule(RawFeatureVectorRule):
    """Validate each carried ETL group's feature-window ordering."""

    name = "group_window"

    def validate(self, raw_feature_vector: RawFeatureVector) -> list[ValidationIssue]:
        """Return errors for group windows that do not move forward in time."""

        issues: list[ValidationIssue] = []
        for group_id, group in raw_feature_vector.groups.items():
            if group.window_start >= group.window_end:
                issues.append(
                    ValidationIssue(
                        code="VAL_INVALID_GROUP_TIME_WINDOW",
                        field_path=f"groups.{group_id}.window_start",
                        message="Group window_start must be before window_end.",
                    )
                )
        return issues


class QualityAnnotationRule(RawFeatureVectorRule):
    """Verify that ETL biomarker values retain matching quality annotations."""

    name = "quality_annotations"
    _domain_names = ("motion", "pressure", "muscle")

    def validate(self, raw_feature_vector: RawFeatureVector) -> list[ValidationIssue]:
        """Return errors when a parsed domain's value and quality keys diverge."""

        issues: list[ValidationIssue] = []
        for group_id, group in raw_feature_vector.groups.items():
            for domain_name in self._domain_names:
                domain = getattr(group, domain_name)
                if domain is None:
                    continue
                if set(domain.biomarkers) != set(domain.quality):
                    issues.append(
                        ValidationIssue(
                            code="VAL_QUALITY_KEY_MISMATCH",
                            field_path=f"groups.{group_id}.{domain_name}",
                            message=(
                                "Each ETL biomarker must retain exactly one "
                                "quality annotation."
                            ),
                        )
                    )
        return issues


DEFAULT_RULES: tuple[RawFeatureVectorRule, ...] = (
    RequiredSectionsRule(),
    IdentityFieldsRule(),
    GroupWindowRule(),
    QualityAnnotationRule(),
)

# Deprecated name retained only so existing callers can migrate without an
# abrupt import failure. Its input contract is RawFeatureVector.
FeatureVectorRule = RawFeatureVectorRule


def _get_nested_value(raw_feature_vector: RawFeatureVector, field_path: str) -> object | None:
    """Resolve a dot-separated field path without mutating the input."""

    value: object | None = raw_feature_vector
    for part in field_path.split("."):
        value = getattr(value, part, None)
        if value is None:
            return None
    return value
