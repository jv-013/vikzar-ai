"""
ValidationRule: the strategy abstraction for one independent, named
quality check.

See docs/development/FEATURE_VALIDATION_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, Tuple

from app.etl.feature_extraction import ExtractedFeatureSet

from .quality import QualityFlag, SetQualityObservation


@dataclass(frozen=True)
class RuleResult:
    """
    One ValidationRule's findings for one ExtractedFeatureSet.

    Attributes
        biomarker_flags: QualityFlag raised per (domain, feature_name)
            pair. A pair absent here means this rule found no concern
            for that biomarker — not that the biomarker is VALID
            overall (other rules may still contribute flags).
        set_observations: Findings not tied to one specific present
            biomarker.
    """

    biomarker_flags: Mapping[Tuple[str, str], QualityFlag]
    set_observations: Sequence[SetQualityObservation] = field(default_factory=tuple)


class ValidationRule(Protocol):
    """
    A single, independently-documented, cross-cutting quality check.

    Purpose
        Evaluate one ExtractedFeatureSet and report findings. Unlike
        FeatureModule (domain-partitioned), a ValidationRule may
        inspect any or all domains — quality concerns like "is this
        value finite" apply uniformly, not per domain.

    Rules needing static, session-level context (e.g. which groups
    have EMG configured) take it via their own constructor, exactly
    like Calibrator/Filterer/Extractor take their domain config — never
    through evaluate()'s signature.
    """

    def evaluate(self, extracted: ExtractedFeatureSet) -> RuleResult:
        """Evaluate one ExtractedFeatureSet and return this rule's findings."""
        ...
