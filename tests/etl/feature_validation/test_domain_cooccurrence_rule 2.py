"""Unit tests for DomainCoOccurrenceRule."""

from __future__ import annotations

from app.etl.feature_validation.quality import QualityFlag
from app.etl.feature_validation.rules.domain_cooccurrence_rule import DomainCoOccurrenceRule

from .helpers import make_extracted_feature_set


def test_flags_mean_jerk_present_without_peak_jerk() -> None:
    extracted = make_extracted_feature_set(
        domains={"motion": {"peak_resultant_acceleration": 5.0, "mean_jerk": 100.0}}
    )

    result = DomainCoOccurrenceRule().evaluate(extracted)

    assert result.biomarker_flags[("motion", "mean_jerk")] == (
        QualityFlag.EXPECTED_COOCCURRING_BIOMARKER_MISSING
    )


def test_does_not_flag_when_both_jerk_biomarkers_present() -> None:
    extracted = make_extracted_feature_set(
        domains={"motion": {"mean_jerk": 100.0, "peak_jerk": 200.0}}
    )

    result = DomainCoOccurrenceRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_does_not_flag_impulse_present_without_loading_rate() -> None:
    """Regression test: PressureFeatures can legitimately produce
    impulse=0.0 without loading_rate on a degenerate (but structurally
    possible) all-same-timestamp window — asserting co-occurrence here
    would be based on a misreading of the actual gating logic."""
    extracted = make_extracted_feature_set(domains={"pressure": {"peak_load": 5.0, "impulse": 0.0}})

    result = DomainCoOccurrenceRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_flags_motion_present_without_pressure() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    result = DomainCoOccurrenceRule().evaluate(extracted)

    assert len(result.set_observations) == 1
    observation = result.set_observations[0]
    assert observation.domain == "pressure"
    assert observation.flag == QualityFlag.EXPECTED_COOCCURRING_BIOMARKER_MISSING


def test_does_not_flag_when_both_motion_and_pressure_present() -> None:
    extracted = make_extracted_feature_set(
        domains={
            "motion": {"peak_resultant_acceleration": 5.0},
            "pressure": {"peak_load": 3.0},
        }
    )

    result = DomainCoOccurrenceRule().evaluate(extracted)

    assert result.set_observations == ()


def test_does_not_flag_when_both_motion_and_pressure_absent() -> None:
    extracted = make_extracted_feature_set(domains={"muscle": {"quadriceps_rms": 1.0}})

    result = DomainCoOccurrenceRule().evaluate(extracted)

    assert result.set_observations == ()
