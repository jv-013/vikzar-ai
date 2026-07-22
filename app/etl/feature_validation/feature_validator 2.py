"""
Feature Validation.

Stage 8 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/FEATURE_VALIDATION_DESIGN.md).

Answers exactly one question: can these extracted biomechanical
biomarkers be trusted? Assesses quality, completeness, internal
consistency, and (where determinable) expected presence — never
meaning. Never estimates injury risk, fatigue, dominant limb, or
movement quality; never compares across synchronization groups. This is
the final ETL quality gate; app/etl/publisher (later) crosses the
ETL->AI boundary into RawFeatureVector. Feature Validation touches
neither.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Dict, List, Mapping, Sequence, Tuple

from app.etl.feature_extraction import ExtractedFeatureSet

from .quality import BiomarkerQuality, QualityFlag, QualityStatus, SetQualityObservation
from .validated_feature_set import ValidatedFeatureSet
from .validation_rule import ValidationRule

logger = logging.getLogger(__name__)

ValidatedFeatureSetConsumer = Callable[[ValidatedFeatureSet], None]
"""Invoked with each ValidatedFeatureSet as it is emitted."""

# Flags indicating a hard, mathematically-impossible violation — a
# biomarker with any of these is REJECTED. Every other flag is a soft
# concern (QUESTIONABLE): the value is still mathematically well-formed,
# only under-supported or context-ambiguous.
_REJECTED_TIER_FLAGS = frozenset(
    {
        QualityFlag.NON_FINITE_VALUE,
        QualityFlag.NEGATIVE_VALUE_IMPOSSIBLE_BY_DEFINITION,
        QualityFlag.INTERNAL_CONSISTENCY_VIOLATED,
    }
)

_FLAG_RATIONALES: Mapping[QualityFlag, str] = {
    QualityFlag.NON_FINITE_VALUE: "Value is NaN or infinite.",
    QualityFlag.NEGATIVE_VALUE_IMPOSSIBLE_BY_DEFINITION: (
        "Value is negative, which is impossible given this biomarker's own "
        "formula (a magnitude, RMS, MAV, or count-over-duration value)."
    ),
    QualityFlag.INTERNAL_CONSISTENCY_VIOLATED: (
        "Value violates a required mathematical ordering with a co-occurring "
        "biomarker in the same domain (e.g. peak below mean)."
    ),
    QualityFlag.EXPECTED_COOCCURRING_BIOMARKER_MISSING: (
        "A biomarker Feature Extraction always computes alongside this one is "
        "missing from this window — indicates a possible upstream regression."
    ),
    QualityFlag.INSUFFICIENT_SAMPLE_COUNT: (
        "Fewer window frames contributed to this domain than the configured "
        "minimum fraction of the window's nominal expected sample count."
    ),
}

_VALID_RATIONALE = "All applicable quality checks passed."


class FeatureValidator:
    """
    Converts ExtractedFeatureSets into ValidatedFeatureSets.

    Purpose
        Run every registered ValidationRule against each
        ExtractedFeatureSet, merge their findings per biomarker, and
        derive an explicit, explainable BiomarkerQuality for every
        biomarker present — never deleting one (Founder Decision 2).

    Statelessness and idempotency
        Stateless across calls, the same as Extractor — every rule is
        a pure function of the ExtractedFeatureSet it is given, so
        FeatureValidator holds no cross-window or cross-group state
        (Founder Decision 5: each group's each window is evaluated in
        isolation). handle()'s isinstance guard is a pure wiring-bug
        catcher, like Extractor's and Calibration's.
    """

    def __init__(
        self,
        rules: Sequence[ValidationRule],
        on_validated: ValidatedFeatureSetConsumer,
    ) -> None:
        """
        Initialize the feature validator.

        Args:
            rules: ValidationRules to run, in no particular required
                order — findings are merged, not sequenced. See
                defaults.default_validation_rules.
            on_validated: Callback invoked with each emitted
                ValidatedFeatureSet.
        """
        self._rules: List[ValidationRule] = list(rules)
        self._on_validated = on_validated

    def handle(self, extracted: ExtractedFeatureSet) -> None:
        """
        Validate a single ExtractedFeatureSet.

        This is the entry point wired as Extractor's on_extracted
        callback. Raises immediately for a wrong input type; every
        other failure is logged and the set is dropped.

        Args:
            extracted: The feature set to validate.

        Raises:
            TypeError: If extracted is not an ExtractedFeatureSet.
        """
        if not isinstance(extracted, ExtractedFeatureSet):
            raise TypeError(
                f"FeatureValidator.handle() only accepts ExtractedFeatureSet; "
                f"received {type(extracted).__name__}."
            )
        try:
            self._handle(extracted)
        except Exception:
            logger.exception(
                "feature_validator.unexpected_error",
                extra={"group_id": extracted.group_id},
            )

    def _handle(self, extracted: ExtractedFeatureSet) -> None:
        biomarker_flags: Dict[Tuple[str, str], List[QualityFlag]] = defaultdict(list)
        set_observations: List[SetQualityObservation] = []

        for rule in self._rules:
            result = rule.evaluate(extracted)
            for key, flag in result.biomarker_flags.items():
                biomarker_flags[key].append(flag)
            set_observations.extend(result.set_observations)

        biomarker_quality: Dict[str, Dict[str, BiomarkerQuality]] = {}
        for domain_name, features in extracted.domains.items():
            biomarker_quality[domain_name] = {
                feature_name: self._assess(biomarker_flags.get((domain_name, feature_name), []))
                for feature_name in features
            }

        validated = ValidatedFeatureSet(
            raw=extracted,
            biomarker_quality=biomarker_quality,
            set_observations=tuple(set_observations),
        )
        self._on_validated(validated)

    def _assess(self, flags: List[QualityFlag]) -> BiomarkerQuality:
        if not flags:
            return BiomarkerQuality(status=QualityStatus.VALID, flags=(), rationale=_VALID_RATIONALE)

        unique_flags = tuple(dict.fromkeys(flags))
        status = (
            QualityStatus.REJECTED
            if any(flag in _REJECTED_TIER_FLAGS for flag in unique_flags)
            else QualityStatus.QUESTIONABLE
        )
        rationale = " ".join(_FLAG_RATIONALES[flag] for flag in unique_flags)
        return BiomarkerQuality(status=status, flags=unique_flags, rationale=rationale)
