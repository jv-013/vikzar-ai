"""
AggregatedFeatureCycle: the internal contract between FeatureSetAggregator
and Publisher.

AggregatedFeatureCycle is an ETL-internal type only, like every other
stage-to-stage type before it. It must never be imported outside
app/etl and has no relationship to RawFeatureVector — Publisher is the
only stage permitted to construct that.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.etl.feature_validation import ValidatedFeatureSet


@dataclass(frozen=True)
class AggregatedFeatureCycle:
    """
    One complete cycle's worth of ValidatedFeatureSets, one per
    configured synchronization group.

    Purpose
        Carry exactly one ValidatedFeatureSet per group to Publisher, so
        Publisher itself never buffers, waits, or reasons about more
        than one already-complete object (Founder Decision: Publisher
        remains stateless).

    Attributes
        groups: One ValidatedFeatureSet per group_id, keyed by that
            group's own group_id (ValidatedFeatureSet.raw.group_id).
            Never merged, compared, or altered relative to one another
            — each entry is exactly the object FeatureValidator
            produced for that group.

    Raises
        ValueError: If groups is empty.
    """

    groups: Mapping[str, ValidatedFeatureSet]

    def __post_init__(self) -> None:
        if not self.groups:
            raise ValueError("AggregatedFeatureCycle.groups must not be empty.")
        object.__setattr__(self, "groups", MappingProxyType(dict(self.groups)))
