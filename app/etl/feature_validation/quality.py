"""
Quality vocabulary shared by every ValidationRule and by
ValidatedFeatureSet.

See docs/development/FEATURE_VALIDATION_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class QualityStatus(str, Enum):
    """
    A biomarker's overall trustworthiness, derived from its QualityFlags.

    VALID
        No flags raised by any ValidationRule.
    QUESTIONABLE
        A soft concern only — the value is mathematically well-formed,
        but under-supported or context-ambiguous (e.g. below the
        configured sample-sufficiency threshold).
    REJECTED
        A hard violation — the value is non-finite, mathematically
        impossible given its own formula, or internally inconsistent
        with a co-occurring biomarker. Indicates a bug or corrupted
        data, not merely uncertainty.

    A REJECTED biomarker is never deleted from ValidatedFeatureSet.raw
    — only annotated. Downstream consumers decide whether to use it
    (Founder Decision 2: confidence, not deletion).
    """

    VALID = "valid"
    QUESTIONABLE = "questionable"
    REJECTED = "rejected"


class QualityFlag(str, Enum):
    """
    A specific, named reason a biomarker's or domain's quality was
    questioned. Every flag has a fixed rationale template in
    feature_validator.py, so a status is always explainable using only
    the recorded flags (Founder Decision 6).
    """

    NON_FINITE_VALUE = "non_finite_value"
    NEGATIVE_VALUE_IMPOSSIBLE_BY_DEFINITION = "negative_value_impossible_by_definition"
    INTERNAL_CONSISTENCY_VIOLATED = "internal_consistency_violated"
    EXPECTED_COOCCURRING_BIOMARKER_MISSING = "expected_cooccurring_biomarker_missing"
    INSUFFICIENT_SAMPLE_COUNT = "insufficient_sample_count"
    EXPECTED_DOMAIN_ABSENT = "expected_domain_absent"
    UNEXPECTED_DOMAIN_PRESENT = "unexpected_domain_present"


@dataclass(frozen=True)
class BiomarkerQuality:
    """
    One biomarker's quality assessment.

    Attributes
        status: Derived from flags — REJECTED if any hard-violation
            flag is present, else QUESTIONABLE if any soft-concern flag
            is present, else VALID.
        flags: Every QualityFlag raised by any rule for this biomarker.
            Empty when status is VALID.
        rationale: A human-readable explanation, always present —
            answers "why was this biomarker accepted/rejected" using
            only this record (Founder Decision 6), independent of
            whether the reader knows the QualityFlag vocabulary.
    """

    status: QualityStatus
    flags: Sequence[QualityFlag]
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "flags", tuple(self.flags))


@dataclass(frozen=True)
class SetQualityObservation:
    """
    A quality finding that is not tied to one specific present
    biomarker — e.g. an entire domain being unexpectedly absent, which
    concerns the shape of the whole ExtractedFeatureSet, not a value
    within it.

    Attributes
        flag: The QualityFlag this observation raised.
        domain: Which domain this observation concerns, when
            applicable (e.g. "muscle" for an absent-domain observation).
            None for observations that concern the whole set.
        rationale: Human-readable explanation, always present.
    """

    flag: QualityFlag
    domain: Optional[str]
    rationale: str
