"""AI-side RawFeatureVector validation utilities for Vikzar AI."""

from app.validation.exceptions import (
    FeatureValidationError,
    InvalidValueError,
    MissingFieldError,
    SchemaValidationError,
    ValidationError,
)
from app.validation.report import ValidationIssue, ValidationReport
from app.validation.validator import (
    FeatureVectorValidator,
    RawFeatureVectorValidator,
    ValidatedRawFeatureVector,
    validate_feature_vector,
    validate_raw_feature_vector,
)

__all__ = [
    "FeatureValidationError",
    "FeatureVectorValidator",
    "InvalidValueError",
    "MissingFieldError",
    "SchemaValidationError",
    "ValidationError",
    "ValidationIssue",
    "ValidationReport",
    "RawFeatureVectorValidator",
    "ValidatedRawFeatureVector",
    "validate_feature_vector",
    "validate_raw_feature_vector",
]
