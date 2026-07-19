"""AI-facing copies of ETL feature-quality annotations."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class QualityStatusInfo(str, Enum):
    """Overall trust classification assigned by ETL feature validation."""

    VALID = "valid"
    QUESTIONABLE = "questionable"
    REJECTED = "rejected"


class QualityFlagInfo(str, Enum):
    """Specific, ETL-assigned explanation for a feature-quality outcome."""

    NON_FINITE_VALUE = "non_finite_value"
    NEGATIVE_VALUE_IMPOSSIBLE_BY_DEFINITION = "negative_value_impossible_by_definition"
    INTERNAL_CONSISTENCY_VIOLATED = "internal_consistency_violated"
    EXPECTED_COOCCURRING_BIOMARKER_MISSING = "expected_cooccurring_biomarker_missing"
    INSUFFICIENT_SAMPLE_COUNT = "insufficient_sample_count"
    EXPECTED_DOMAIN_ABSENT = "expected_domain_absent"
    UNEXPECTED_DOMAIN_PRESENT = "unexpected_domain_present"


class BiomarkerQualityInfo(BaseModel):
    """ETL quality information carried losslessly for one biomarker."""

    status: QualityStatusInfo
    flags: tuple[QualityFlagInfo, ...]
    rationale: str


class SetQualityObservationInfo(BaseModel):
    """ETL quality information concerning a domain or complete feature set."""

    flag: QualityFlagInfo
    domain: str | None
    rationale: str
