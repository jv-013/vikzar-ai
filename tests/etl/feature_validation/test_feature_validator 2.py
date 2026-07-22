"""Unit tests for FeatureValidator."""

from __future__ import annotations

import math
from typing import List

import pytest

from app.etl.feature_validation import (
    QualityFlag,
    QualityStatus,
    RuleResult,
    ValidatedFeatureSet,
)
from app.etl.feature_validation.feature_validator import FeatureValidator
from app.etl.feature_validation.rules.finite_value_rule import FiniteValueRule
from app.etl.feature_validation.rules.sufficiency_rule import SufficiencyRule

from .helpers import make_extracted_feature_set


class _FakeRule:
    def __init__(self, flag: QualityFlag, key=("motion", "peak_resultant_acceleration")):
        self._flag = flag
        self._key = key

    def evaluate(self, extracted) -> RuleResult:
        return RuleResult(biomarker_flags={self._key: self._flag})


def _validator(on_validated, rules) -> FeatureValidator:
    return FeatureValidator(rules=rules, on_validated=on_validated)


def test_valid_when_no_rules_trigger() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    validator = _validator(validated_sets.append, rules=[])
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    validator.handle(extracted)

    quality = validated_sets[0].biomarker_quality["motion"]["peak_resultant_acceleration"]
    assert quality.status == QualityStatus.VALID
    assert quality.flags == ()


def test_merges_flags_from_multiple_rules_onto_the_same_biomarker() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    rules = [
        _FakeRule(QualityFlag.EXPECTED_COOCCURRING_BIOMARKER_MISSING),
        _FakeRule(QualityFlag.INSUFFICIENT_SAMPLE_COUNT),
    ]
    validator = _validator(validated_sets.append, rules=rules)
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    validator.handle(extracted)

    quality = validated_sets[0].biomarker_quality["motion"]["peak_resultant_acceleration"]
    assert set(quality.flags) == {
        QualityFlag.EXPECTED_COOCCURRING_BIOMARKER_MISSING,
        QualityFlag.INSUFFICIENT_SAMPLE_COUNT,
    }


def test_rejected_status_when_a_hard_violation_flag_is_present() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    validator = _validator(validated_sets.append, rules=[FiniteValueRule()])
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": math.nan}})

    validator.handle(extracted)

    quality = validated_sets[0].biomarker_quality["motion"]["peak_resultant_acceleration"]
    assert quality.status == QualityStatus.REJECTED


def test_questionable_status_when_only_a_soft_concern_flag_is_present() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    rule = SufficiencyRule(minimum_fraction=0.5, nominal_sample_interval_ms=10.0)
    validator = _validator(validated_sets.append, rules=[rule])
    extracted = make_extracted_feature_set(
        domains={"motion": {"peak_resultant_acceleration": 5.0}}, sample_counts={"motion": 1}
    )

    validator.handle(extracted)

    quality = validated_sets[0].biomarker_quality["motion"]["peak_resultant_acceleration"]
    assert quality.status == QualityStatus.QUESTIONABLE


def test_rejected_overrides_questionable_when_both_present() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    rules = [
        _FakeRule(QualityFlag.INSUFFICIENT_SAMPLE_COUNT),  # soft
        _FakeRule(QualityFlag.NON_FINITE_VALUE),  # hard
    ]
    validator = _validator(validated_sets.append, rules=rules)
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    validator.handle(extracted)

    quality = validated_sets[0].biomarker_quality["motion"]["peak_resultant_acceleration"]
    assert quality.status == QualityStatus.REJECTED


def test_raw_is_never_mutated() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    validator = _validator(validated_sets.append, rules=[FiniteValueRule()])
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": math.nan}})

    validator.handle(extracted)

    # Even a REJECTED biomarker's value survives unchanged in raw —
    # Feature Validation never deletes or replaces (Founder Decision 7).
    assert validated_sets[0].raw is extracted
    assert math.isnan(validated_sets[0].raw.domains["motion"]["peak_resultant_acceleration"])


def test_set_observations_are_collected_from_rules() -> None:
    class _ObservationOnlyRule:
        def evaluate(self, extracted) -> RuleResult:
            from app.etl.feature_validation.quality import SetQualityObservation

            return RuleResult(
                biomarker_flags={},
                set_observations=(
                    SetQualityObservation(
                        flag=QualityFlag.EXPECTED_DOMAIN_ABSENT, domain="muscle", rationale="test"
                    ),
                ),
            )

    validated_sets: List[ValidatedFeatureSet] = []
    validator = _validator(validated_sets.append, rules=[_ObservationOnlyRule()])
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    validator.handle(extracted)

    assert len(validated_sets[0].set_observations) == 1
    assert validated_sets[0].set_observations[0].domain == "muscle"


def test_handle_raises_type_error_for_non_extracted_feature_set_input() -> None:
    validator = _validator(lambda validated: None, rules=[])

    with pytest.raises(TypeError):
        validator.handle("not an extracted feature set")  # type: ignore[arg-type]


def test_handle_raises_type_error_for_a_validated_feature_set_fed_back_in() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    validator = _validator(validated_sets.append, rules=[])
    validator.handle(make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}}))
    assert validated_sets

    with pytest.raises(TypeError):
        validator.handle(validated_sets[0])  # type: ignore[arg-type]


def test_handle_never_raises_when_a_rule_raises_internally() -> None:
    class ExplodingRule:
        def evaluate(self, extracted):
            raise RuntimeError("simulated rule failure")

    validated_sets: List[ValidatedFeatureSet] = []
    validator = _validator(validated_sets.append, rules=[ExplodingRule()])

    validator.handle(
        make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})
    )  # must not raise

    assert validated_sets == []


def test_deterministic_across_repeated_calls() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    validator = _validator(validated_sets.append, rules=[FiniteValueRule()])
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    validator.handle(extracted)
    validator.handle(extracted)

    first, second = validated_sets
    assert first.biomarker_quality == second.biomarker_quality
