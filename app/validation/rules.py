"""Semantic validation rules for AI FeatureVector input."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.feature_vector import FeatureVector
from app.validation.report import ValidationIssue


class FeatureVectorRule(ABC):
    """Base class for FeatureVector validation rules.

    Parameters:
        None.

    Returns:
        A reusable validation rule instance.

    Exceptions:
        None.
    """

    name: str

    @abstractmethod
    def validate(self, feature_vector: FeatureVector) -> list[ValidationIssue]:
        """Validate a FeatureVector and return discovered issues.

        Parameters:
            feature_vector: Parsed FeatureVector entering the AI pipeline.

        Returns:
            Validation issues found by this rule. An empty list means pass.

        Exceptions:
            None.
        """


class RequiredSectionsRule(FeatureVectorRule):
    """Validate that top-level FeatureVector sections are present."""

    name = "required_sections"

    _sections = (
        "metadata",
        "player",
        "session",
        "imu",
        "fsr",
        "emg",
        "muscles",
        "derived",
        "symmetry",
        "context",
        "labels",
        "system",
    )

    def validate(self, feature_vector: FeatureVector) -> list[ValidationIssue]:
        """Validate required top-level FeatureVector sections.

        Parameters:
            feature_vector: Parsed FeatureVector entering the AI pipeline.

        Returns:
            Error issues for missing or null top-level sections.

        Exceptions:
            None.
        """

        issues: list[ValidationIssue] = []
        for section in self._sections:
            if getattr(feature_vector, section, None) is None:
                issues.append(
                    ValidationIssue(
                        code="VAL_REQUIRED_SECTION",
                        field_path=section,
                        message=f"FeatureVector section '{section}' is required.",
                    )
                )
        return issues


class IdentityFieldsRule(FeatureVectorRule):
    """Validate required identity and context strings."""

    name = "identity_fields"

    _field_paths = (
        "metadata.feature_vector_id",
        "player.player_id",
        "player.sex",
        "player.dominant_leg",
        "player.position",
        "session.session_id",
        "system.source",
    )

    def validate(self, feature_vector: FeatureVector) -> list[ValidationIssue]:
        """Validate non-empty identity fields required by downstream AI.

        Parameters:
            feature_vector: Parsed FeatureVector entering the AI pipeline.

        Returns:
            Error issues for blank identity fields.

        Exceptions:
            None.
        """

        issues: list[ValidationIssue] = []
        for field_path in self._field_paths:
            value = _get_nested_value(feature_vector, field_path)
            if not isinstance(value, str) or not value.strip():
                issues.append(
                    ValidationIssue(
                        code="VAL_EMPTY_IDENTITY_FIELD",
                        field_path=field_path,
                        message=f"Field '{field_path}' must be a non-empty string.",
                    )
                )
        return issues


class FiniteNumbersRule(FeatureVectorRule):
    """Validate that numeric FeatureVector values are finite."""

    name = "finite_numbers"

    def validate(self, feature_vector: FeatureVector) -> list[ValidationIssue]:
        """Validate that all numeric values are finite.

        Parameters:
            feature_vector: Parsed FeatureVector entering the AI pipeline.

        Returns:
            Error issues for NaN or infinite numeric fields.

        Exceptions:
            None.
        """

        issues: list[ValidationIssue] = []
        for field_path, value in _iter_numeric_fields(feature_vector):
            if not math.isfinite(float(value)):
                issues.append(
                    ValidationIssue(
                        code="VAL_NON_FINITE_NUMBER",
                        field_path=field_path,
                        message=f"Field '{field_path}' must be finite.",
                    )
                )
        return issues


class MetadataTimeWindowRule(FeatureVectorRule):
    """Validate timestamp and feature-window consistency."""

    name = "metadata_time_window"

    def validate(self, feature_vector: FeatureVector) -> list[ValidationIssue]:
        """Validate metadata timestamp consistency.

        Parameters:
            feature_vector: Parsed FeatureVector entering the AI pipeline.

        Returns:
            Error issues when the window is invalid or timestamp is outside it.

        Exceptions:
            None.
        """

        metadata = feature_vector.metadata
        issues: list[ValidationIssue] = []

        if metadata.window_start >= metadata.window_end:
            issues.append(
                ValidationIssue(
                    code="VAL_INVALID_TIME_WINDOW",
                    field_path="metadata.window_start",
                    message="FeatureVector window_start must be before window_end.",
                )
            )

        if not _timestamp_inside_window(
            metadata.timestamp,
            metadata.window_start,
            metadata.window_end,
        ):
            issues.append(
                ValidationIssue(
                    code="VAL_TIMESTAMP_OUTSIDE_WINDOW",
                    field_path="metadata.timestamp",
                    message="FeatureVector timestamp must fall within its window.",
                )
            )

        return issues


class SystemValidationRule(FeatureVectorRule):
    """Validate ETL validation status carried in system metadata."""

    name = "system_validation"

    def validate(self, feature_vector: FeatureVector) -> list[ValidationIssue]:
        """Validate system-level readiness for AI processing.

        Parameters:
            feature_vector: Parsed FeatureVector entering the AI pipeline.

        Returns:
            Error issues when ETL marked the FeatureVector invalid.

        Exceptions:
            None.
        """

        if feature_vector.system.validation_status:
            return []

        return [
            ValidationIssue(
                code="VAL_ETL_VALIDATION_FAILED",
                field_path="system.validation_status",
                message="FeatureVector was marked invalid before AI validation.",
            )
        ]


class InternalConsistencyRule(FeatureVectorRule):
    """Validate simple cross-field consistency inside FeatureVector sections."""

    name = "internal_consistency"

    def validate(self, feature_vector: FeatureVector) -> list[ValidationIssue]:
        """Validate internal consistency of related fields.

        Parameters:
            feature_vector: Parsed FeatureVector entering the AI pipeline.

        Returns:
            Error issues for inconsistent related values.

        Exceptions:
            None.
        """

        issues: list[ValidationIssue] = []
        fsr = feature_vector.fsr
        emg = feature_vector.emg

        if fsr.min_load > fsr.mean_load:
            issues.append(
                ValidationIssue(
                    code="VAL_INCONSISTENT_FSR_LOAD",
                    field_path="fsr.min_load",
                    message="FSR min_load must not exceed mean_load.",
                )
            )

        if fsr.mean_load > fsr.peak_load:
            issues.append(
                ValidationIssue(
                    code="VAL_INCONSISTENT_FSR_LOAD",
                    field_path="fsr.mean_load",
                    message="FSR mean_load must not exceed peak_load.",
                )
            )

        if emg.mean_activation > emg.peak_activation:
            issues.append(
                ValidationIssue(
                    code="VAL_INCONSISTENT_EMG_ACTIVATION",
                    field_path="emg.mean_activation",
                    message="EMG mean_activation must not exceed peak_activation.",
                )
            )

        if emg.rms_activation > emg.peak_activation:
            issues.append(
                ValidationIssue(
                    code="VAL_INCONSISTENT_EMG_ACTIVATION",
                    field_path="emg.rms_activation",
                    message="EMG rms_activation must not exceed peak_activation.",
                )
            )

        return issues


DEFAULT_RULES: tuple[FeatureVectorRule, ...] = (
    RequiredSectionsRule(),
    IdentityFieldsRule(),
    FiniteNumbersRule(),
    MetadataTimeWindowRule(),
    SystemValidationRule(),
    InternalConsistencyRule(),
)


def _get_nested_value(model: BaseModel, field_path: str) -> Any:
    """Get a nested Pydantic model value from a dot-separated path.

    Parameters:
        model: Root Pydantic model.
        field_path: Dot-separated field path.

    Returns:
        The resolved field value, or None when any path segment is absent.

    Exceptions:
        None.
    """

    value: Any = model
    for part in field_path.split("."):
        value = getattr(value, part, None)
        if value is None:
            return None
    return value


def _iter_numeric_fields(value: Any, path: str = "") -> Iterable[tuple[str, int | float]]:
    """Iterate over numeric values in a nested Pydantic model.

    Parameters:
        value: Current object being inspected.
        path: Dot-separated path to the current value.

    Returns:
        Iterable of field paths and numeric values.

    Exceptions:
        None.
    """

    if isinstance(value, BaseModel):
        for field_name in _model_field_names(value):
            child_path = field_name if not path else f"{path}.{field_name}"
            yield from _iter_numeric_fields(getattr(value, field_name), child_path)
        return

    if isinstance(value, dict):
        for key, child_value in value.items():
            child_path = str(key) if not path else f"{path}.{key}"
            yield from _iter_numeric_fields(child_value, child_path)
        return

    if isinstance(value, list | tuple):
        for index, child_value in enumerate(value):
            child_path = f"{path}[{index}]"
            yield from _iter_numeric_fields(child_value, child_path)
        return

    if isinstance(value, bool):
        return

    if isinstance(value, int | float):
        yield path, value


def _model_field_names(model: BaseModel) -> tuple[str, ...]:
    """Return Pydantic model field names across Pydantic versions.

    Parameters:
        model: Pydantic model instance.

    Returns:
        Tuple of field names defined on the model.

    Exceptions:
        None.
    """

    model_class = model.__class__
    if hasattr(model_class, "model_fields"):
        return tuple(model_class.model_fields.keys())  # type: ignore[attr-defined]
    return tuple(model_class.__fields__.keys())


def _timestamp_inside_window(
    timestamp: datetime,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    """Return whether a timestamp falls inside an inclusive time window.

    Parameters:
        timestamp: FeatureVector timestamp.
        window_start: Start of the feature extraction window.
        window_end: End of the feature extraction window.

    Returns:
        True when timestamp is inside the window; otherwise False.

    Exceptions:
        None.
    """

    return window_start <= timestamp <= window_end
