"""
Feature Validation package.

Stage 8 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/FEATURE_VALIDATION_DESIGN.md.

ValidatedFeatureSet is exported for use elsewhere within app/etl (e.g.
the future Publisher stage). It must never be imported outside app/etl.
"""

from .defaults import default_validation_rules
from .feature_validator import FeatureValidator, ValidatedFeatureSetConsumer
from .quality import BiomarkerQuality, QualityFlag, QualityStatus, SetQualityObservation
from .validated_feature_set import ValidatedFeatureSet
from .validation_rule import RuleResult, ValidationRule

__all__ = [
    "FeatureValidator",
    "ValidatedFeatureSetConsumer",
    "ValidatedFeatureSet",
    "BiomarkerQuality",
    "QualityStatus",
    "QualityFlag",
    "SetQualityObservation",
    "ValidationRule",
    "RuleResult",
    "default_validation_rules",
]
