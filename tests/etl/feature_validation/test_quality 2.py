"""Unit tests for the quality value objects."""

from __future__ import annotations

from app.etl.feature_validation.quality import (
    BiomarkerQuality,
    QualityFlag,
    QualityStatus,
    SetQualityObservation,
)


def test_biomarker_quality_flags_are_stored_as_a_tuple() -> None:
    quality = BiomarkerQuality(
        status=QualityStatus.REJECTED,
        flags=[QualityFlag.NON_FINITE_VALUE],
        rationale="test",
    )

    assert isinstance(quality.flags, tuple)


def test_valid_biomarker_quality_has_no_flags() -> None:
    quality = BiomarkerQuality(status=QualityStatus.VALID, flags=[], rationale="ok")

    assert quality.flags == ()


def test_set_quality_observation_construction() -> None:
    observation = SetQualityObservation(
        flag=QualityFlag.EXPECTED_DOMAIN_ABSENT, domain="muscle", rationale="test"
    )

    assert observation.domain == "muscle"
