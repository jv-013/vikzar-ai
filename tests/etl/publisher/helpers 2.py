"""
Test-only factories for Publisher tests.

Not shipped production code — mirrors the role helpers.py plays for
every other ETL stage's tests. Relies on this directory's conftest.py
to make app.schemas submodules importable (works around
app/schemas/__init__.py being unconditionally broken — see conftest.py
for the full explanation).
"""

from __future__ import annotations

from typing import Mapping, Optional

from app.etl.aggregation import AggregatedFeatureCycle
from app.etl.feature_extraction import ExtractedFeatureSet
from app.etl.feature_validation import BiomarkerQuality, QualityStatus, ValidatedFeatureSet
from app.etl.publisher import PlayerSessionContext
from app.schemas.player import Player
from app.schemas.session import Session


def make_extracted_feature_set(
    group_id: str = "left_lower_limb",
    window_specification_name: str = "primary",
    window_start: float = 0.0,
    window_end: float = 1000.0,
    domains: Optional[Mapping[str, Mapping[str, float]]] = None,
    sample_counts: Optional[Mapping[str, int]] = None,
) -> ExtractedFeatureSet:
    if domains is None:
        domains = {"motion": {"peak_resultant_acceleration": 5.0}}
    if sample_counts is None:
        sample_counts = {name: 10 for name in domains}
    return ExtractedFeatureSet(
        group_id=group_id,
        window_specification_name=window_specification_name,
        window_start=window_start,
        window_end=window_end,
        domains=domains,
        sample_counts=sample_counts,
    )


def make_validated_feature_set(
    group_id: str = "left_lower_limb",
    window_start: float = 0.0,
    window_end: float = 1000.0,
    domains: Optional[Mapping[str, Mapping[str, float]]] = None,
    biomarker_quality: Optional[Mapping[str, Mapping[str, BiomarkerQuality]]] = None,
    set_observations=(),
) -> ValidatedFeatureSet:
    extracted = make_extracted_feature_set(
        group_id=group_id, window_start=window_start, window_end=window_end, domains=domains
    )
    if biomarker_quality is None:
        valid = BiomarkerQuality(status=QualityStatus.VALID, flags=(), rationale="ok")
        biomarker_quality = {
            domain_name: {feature_name: valid for feature_name in features}
            for domain_name, features in extracted.domains.items()
        }
    return ValidatedFeatureSet(
        raw=extracted, biomarker_quality=biomarker_quality, set_observations=set_observations
    )


def make_aggregated_feature_cycle(
    groups: Optional[Mapping[str, ValidatedFeatureSet]] = None,
) -> AggregatedFeatureCycle:
    if groups is None:
        groups = {"left_lower_limb": make_validated_feature_set(group_id="left_lower_limb")}
    return AggregatedFeatureCycle(groups=groups)


def make_player_session_context(**overrides) -> PlayerSessionContext:
    defaults = dict(
        player=Player(player_id="p1", age=22, sex="M", dominant_leg="right", position="forward"),
        session=Session(session_id="s1"),
        firmware_revision="fw-1.0.0",
        hardware_revision="hw-v1",
        protocol_version="1",
        schema_version="1.0.0",
        source="vikzar_etl_v1",
    )
    defaults.update(overrides)
    return PlayerSessionContext(**defaults)
