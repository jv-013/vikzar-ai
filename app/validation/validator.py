"""Validation boundary for ETL-owned RawFeatureVectors entering AI."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias

from pydantic import ValidationError as PydanticValidationError

from app.schemas.raw_feature_vector import RawFeatureVector
from app.validation.exceptions import (
    FeatureValidationError,
    SchemaValidationError,
    ValidationError,
)
from app.validation.report import ValidationReport
from app.validation.rules import DEFAULT_RULES, RawFeatureVectorRule


logger = logging.getLogger("app.validation")

# The alias makes the trust boundary explicit without allocating or mapping a
# second object. Only validate_raw_feature_vector creates this runtime type.
ValidatedRawFeatureVector: TypeAlias = RawFeatureVector


class RawFeatureVectorValidator:
    """Validate ETL-owned RawFeatureVectors before downstream AI processing."""

    def __init__(self, rules: Sequence[RawFeatureVectorRule] | None = None) -> None:
        """Create a validator using injected rules or the production defaults."""

        self._rules: tuple[RawFeatureVectorRule, ...] = tuple(rules or DEFAULT_RULES)

    def validate(
        self,
        raw_feature_vector: RawFeatureVector | Mapping[str, Any],
    ) -> ValidationReport:
        """Return a structured report for one RawFeatureVector input."""

        parsed_vector = self._parse_raw_feature_vector(raw_feature_vector)
        report = ValidationReport()

        for rule in self._rules:
            try:
                report.extend(rule.validate(parsed_vector))
            except Exception as exc:
                self._log_unexpected_rule_failure(rule, parsed_vector, exc)
                raise ValidationError(
                    f"Validation rule '{rule.name}' failed unexpectedly."
                ) from exc

        self._log_report(parsed_vector, report)
        return report

    def validate_or_raise(
        self,
        raw_feature_vector: RawFeatureVector | Mapping[str, Any],
    ) -> ValidatedRawFeatureVector:
        """Validate input and return the explicit ETL-to-AI trusted contract."""

        parsed_vector = self._parse_raw_feature_vector(raw_feature_vector)
        report = self.validate(parsed_vector)
        if report.is_valid:
            return parsed_vector
        raise FeatureValidationError(
            "RawFeatureVector failed AI validation.",
            report=report,
            issues=report.errors,
        )

    def _parse_raw_feature_vector(
        self,
        raw_feature_vector: RawFeatureVector | Mapping[str, Any],
    ) -> RawFeatureVector:
        """Parse supported input into the locked RawFeatureVector schema."""

        if isinstance(raw_feature_vector, RawFeatureVector):
            return raw_feature_vector
        if not isinstance(raw_feature_vector, Mapping):
            raise SchemaValidationError(
                "Validation input must be a RawFeatureVector or mapping."
            )
        try:
            return _parse_model(RawFeatureVector, raw_feature_vector)
        except PydanticValidationError as exc:
            logger.warning(
                "RawFeatureVector schema validation failed.",
                extra={"component": "validation", "error_count": len(exc.errors())},
            )
            raise SchemaValidationError(
                "Input does not match the RawFeatureVector schema."
            ) from exc

    @staticmethod
    def _log_report(
        raw_feature_vector: RawFeatureVector,
        report: ValidationReport,
    ) -> None:
        """Log validation outcome without recording ETL biomarker values."""

        log_data = {
            "component": "validation",
            "feature_vector_id": raw_feature_vector.feature_vector_id,
            "player_id": raw_feature_vector.player.player_id,
            "session_id": raw_feature_vector.session.session_id,
            "is_valid": report.is_valid,
            "error_count": report.error_count,
            "warning_count": report.warning_count,
        }
        if report.is_valid:
            logger.info("RawFeatureVector validation passed.", extra=log_data)
        else:
            logger.warning("RawFeatureVector validation failed.", extra=log_data)

    @staticmethod
    def _log_unexpected_rule_failure(
        rule: RawFeatureVectorRule,
        raw_feature_vector: RawFeatureVector,
        exc: Exception,
    ) -> None:
        """Log unexpected rule failures with structured context."""

        logger.exception(
            "RawFeatureVector validation rule failed unexpectedly.",
            extra={
                "component": "validation",
                "rule": rule.name,
                "feature_vector_id": raw_feature_vector.feature_vector_id,
                "exception_type": exc.__class__.__name__,
            },
        )


def validate_raw_feature_vector(
    raw_feature_vector: RawFeatureVector | Mapping[str, Any],
) -> ValidatedRawFeatureVector:
    """Validate ETL output and return the trusted runtime contract."""

    return RawFeatureVectorValidator().validate_or_raise(raw_feature_vector)


# Deprecated names retained for a non-breaking API migration. They validate
# RawFeatureVector inputs and must not be used to revive the legacy contract.
FeatureVectorValidator = RawFeatureVectorValidator
validate_feature_vector = validate_raw_feature_vector


def _parse_model(
    model_type: type[RawFeatureVector],
    data: Mapping[str, Any],
) -> RawFeatureVector:
    """Parse a mapping into a Pydantic model across supported versions."""

    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(data)  # type: ignore[attr-defined]
    return model_type.parse_obj(data)
