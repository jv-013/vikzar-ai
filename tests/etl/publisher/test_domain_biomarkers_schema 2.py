"""Unit tests for app.schemas.domain_biomarkers.DomainBiomarkers."""

from __future__ import annotations

import pytest

from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.quality_info import BiomarkerQualityInfo, QualityStatusInfo

_VALID = BiomarkerQualityInfo(status=QualityStatusInfo.VALID, flags=[], rationale="ok")


def test_permits_matching_keys() -> None:
    domain = DomainBiomarkers(biomarkers={"peak_resultant_acceleration": 5.0}, quality={"peak_resultant_acceleration": _VALID})
    assert domain.biomarkers["peak_resultant_acceleration"] == 5.0


def test_rejects_mismatched_keys() -> None:
    with pytest.raises(ValueError):
        DomainBiomarkers(biomarkers={"peak_resultant_acceleration": 5.0}, quality={"a_different_name": _VALID})
