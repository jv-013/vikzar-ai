"""Tests for the locked RawFeatureVector ETL-to-AI contract."""

from __future__ import annotations

from datetime import datetime, timezone
import math

import pytest
from pydantic import ValidationError

from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.group_feature_set import GroupFeatureSet
from app.schemas.hardware_provenance import HardwareProvenance
from app.schemas.player import Player
from app.schemas.quality_info import BiomarkerQualityInfo, QualityFlagInfo, QualityStatusInfo
from app.schemas.raw_feature_vector import RawFeatureVector
from app.schemas.session import Session


def _quality(status: QualityStatusInfo = QualityStatusInfo.VALID) -> BiomarkerQualityInfo:
    """Return ETL quality metadata for a single test biomarker."""

    return BiomarkerQualityInfo(status=status, flags=(), rationale="ETL annotation.")


def test_domain_biomarkers_rejects_mismatched_quality_keys() -> None:
    """Each ETL biomarker must preserve a quality annotation with the same name."""

    with pytest.raises(ValidationError):
        DomainBiomarkers(
            biomarkers={"peak_resultant_acceleration": 5.0},
            quality={"different_key": _quality()},
        )


def test_raw_feature_vector_preserves_rejected_values_and_quality_metadata() -> None:
    """RawFeatureVector carries ETL values losslessly without AI replacement."""

    raw_feature_vector = RawFeatureVector(
        feature_vector_id="rfv-001",
        timestamp=datetime(2026, 7, 19, tzinfo=timezone.utc),
        schema_version="1.0.0",
        source="vikzar_etl_v1",
        player=Player(
            player_id="player-001",
            age=24,
            sex="male",
            dominant_leg="right",
            position="forward",
        ),
        session=Session(session_id="session-001"),
        hardware=HardwareProvenance(
            firmware_revision="fw-1.0.0",
            hardware_revision="hw-v1",
            protocol_version="1",
        ),
        groups={
            "left_lower_limb": GroupFeatureSet(
                window_start=0.0,
                window_end=1000.0,
                motion=DomainBiomarkers(
                    biomarkers={"peak_resultant_acceleration": math.nan},
                    quality={
                        "peak_resultant_acceleration": BiomarkerQualityInfo(
                            status=QualityStatusInfo.REJECTED,
                            flags=(QualityFlagInfo.NON_FINITE_VALUE,),
                            rationale="ETL rejected the non-finite feature.",
                        )
                    },
                ),
            )
        },
    )

    motion = raw_feature_vector.groups["left_lower_limb"].motion
    assert motion is not None
    assert math.isnan(motion.biomarkers["peak_resultant_acceleration"])
    assert motion.quality["peak_resultant_acceleration"].status is QualityStatusInfo.REJECTED
