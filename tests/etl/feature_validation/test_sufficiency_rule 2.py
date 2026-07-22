"""Unit tests for SufficiencyRule."""

from __future__ import annotations

import pytest

from app.etl.feature_validation.quality import QualityFlag
from app.etl.feature_validation.rules.sufficiency_rule import SufficiencyRule

from .helpers import make_extracted_feature_set


def _rule() -> SufficiencyRule:
    # window duration 1000ms, nominal interval 10ms -> nominal_count=100,
    # 0.5 fraction -> required = 50.
    return SufficiencyRule(minimum_fraction=0.5, nominal_sample_interval_ms=10.0)


def test_flags_domain_below_required_sample_count() -> None:
    extracted = make_extracted_feature_set(
        domains={"motion": {"peak_resultant_acceleration": 5.0}},
        sample_counts={"motion": 49},
    )

    result = _rule().evaluate(extracted)

    assert result.biomarker_flags[("motion", "peak_resultant_acceleration")] == (
        QualityFlag.INSUFFICIENT_SAMPLE_COUNT
    )


def test_does_not_flag_domain_at_required_sample_count() -> None:
    extracted = make_extracted_feature_set(
        domains={"motion": {"peak_resultant_acceleration": 5.0}},
        sample_counts={"motion": 50},
    )

    result = _rule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_flags_every_biomarker_in_an_insufficient_domain() -> None:
    extracted = make_extracted_feature_set(
        domains={"motion": {"peak_resultant_acceleration": 5.0, "mean_resultant_acceleration": 3.0}},
        sample_counts={"motion": 1},
    )

    result = _rule().evaluate(extracted)

    assert len(result.biomarker_flags) == 2


def test_rejects_out_of_range_minimum_fraction() -> None:
    with pytest.raises(ValueError):
        SufficiencyRule(minimum_fraction=0.0, nominal_sample_interval_ms=10.0)
    with pytest.raises(ValueError):
        SufficiencyRule(minimum_fraction=1.5, nominal_sample_interval_ms=10.0)


def test_rejects_non_positive_nominal_sample_interval() -> None:
    with pytest.raises(ValueError):
        SufficiencyRule(minimum_fraction=0.5, nominal_sample_interval_ms=0.0)
