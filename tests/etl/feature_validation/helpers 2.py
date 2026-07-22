"""
Test-only ExtractedFeatureSet factory for Feature Validation tests.

Not shipped production code — mirrors the role helpers.py plays for
every other ETL stage's tests.
"""

from __future__ import annotations

from typing import Mapping, Optional

from app.etl.feature_extraction import ExtractedFeatureSet


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
