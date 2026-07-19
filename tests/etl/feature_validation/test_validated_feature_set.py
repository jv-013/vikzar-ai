"""Unit tests for ValidatedFeatureSet."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.etl.feature_validation.quality import BiomarkerQuality, QualityStatus
from app.etl.feature_validation.validated_feature_set import ValidatedFeatureSet

from .helpers import make_extracted_feature_set

_VALID = BiomarkerQuality(status=QualityStatus.VALID, flags=(), rationale="ok")


def test_rejects_mismatched_domain_keys() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    with pytest.raises(ValueError):
        ValidatedFeatureSet(
            raw=extracted,
            biomarker_quality={"pressure": {}},
            set_observations=(),
        )


def test_rejects_mismatched_feature_name_keys_within_a_domain() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    with pytest.raises(ValueError):
        ValidatedFeatureSet(
            raw=extracted,
            biomarker_quality={"motion": {"a_different_feature_name": _VALID}},
            set_observations=(),
        )


def test_permits_fully_matching_structure() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    validated = ValidatedFeatureSet(
        raw=extracted,
        biomarker_quality={"motion": {"peak_resultant_acceleration": _VALID}},
        set_observations=(),
    )

    assert validated.raw is extracted


def test_biomarker_quality_is_immutable() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})
    validated = ValidatedFeatureSet(
        raw=extracted,
        biomarker_quality={"motion": {"peak_resultant_acceleration": _VALID}},
        set_observations=(),
    )

    assert isinstance(validated.biomarker_quality, MappingProxyType)
    with pytest.raises(TypeError):
        validated.biomarker_quality["pressure"] = {}


def test_set_observations_is_a_tuple() -> None:
    extracted = make_extracted_feature_set(domains={})
    validated = ValidatedFeatureSet(raw=extracted, biomarker_quality={}, set_observations=[])

    assert isinstance(validated.set_observations, tuple)
