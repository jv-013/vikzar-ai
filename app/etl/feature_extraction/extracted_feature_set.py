"""
ExtractedFeatureSet: the internal contract between Feature Extraction
and Feature Validation.

ExtractedFeatureSet is an ETL-internal type only, like RawPacket,
ValidatedPacket, SynchronizedFrame, CalibratedFrame, FilteredFrame, and
Window. It must never be imported outside app/etl and has no
relationship to RawFeatureVector or EnhancedFeatureVector — that
boundary crossing happens later, in app/etl/publisher.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ExtractedFeatureSet:
    """
    One Window's computed, uninterpreted numerical features.

    Purpose
        Carry Feature Extraction's output to Feature Validation. Every
        feature is a measurable quantity; none is an inference,
        classification, or judgment (Founder Decision 1).

    Provenance
        group_id, window_specification_name, window_start, window_end
        are carried unchanged from the source Window — this alone
        establishes traceability back to the originating Window,
        synchronization group, and time interval. Traceability back to
        originating sensor channels is established by documentation,
        not a runtime field: each FeatureModule's own docstring states
        exactly which channels it reads. That mapping is a static fact
        of the pipeline's own code, not data that varies per Window, so
        recording it again per-instance would duplicate information
        already fully determined by which FeatureModule produced a
        given domain's entry.

    sample_counts (Decision 029)
        A scoped, authorized exception to the Feature Extraction
        freeze, added specifically so Feature Validation can make
        scientifically defensible sufficiency assessments (RMS, MAV,
        cadence, jerk, impulse, loading rate, and future frequency-
        domain biomarkers all depend on how many samples actually
        contributed). Metadata only — an integer count per domain,
        never a second copy of the raw samples or the feature values
        themselves. See docs/architecture/10_SYSTEM_DECISIONS.md,
        Decision 029.

    Attributes
        group_id: Preserved unchanged from the source Window.
        window_specification_name: Preserved unchanged from the source
            Window.
        window_start: Preserved unchanged from the source Window.
        window_end: Preserved unchanged from the source Window.
        domains: Computed features keyed by domain name (e.g. "motion",
            "pressure", "muscle"), each a {feature_name: value} mapping.
            A domain is present only when its FeatureModule produced at
            least one feature for this window — e.g. "muscle" is absent
            entirely for a Match Mode group's window, never a
            zero-filled placeholder.
        sample_counts: How many window frames contributed usable data
            to each domain, keyed identically to domains — a domain key
            appears here if and only if it appears in domains.

    Raises
        ValueError: If group_id or window_specification_name is empty,
            window_end <= window_start, or sample_counts' keys do not
            exactly match domains' keys.
    """

    group_id: str
    window_specification_name: str
    window_start: float
    window_end: float
    domains: Mapping[str, Mapping[str, float]]
    sample_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("ExtractedFeatureSet.group_id must not be empty.")
        if not self.window_specification_name:
            raise ValueError(
                "ExtractedFeatureSet.window_specification_name must not be empty."
            )
        if self.window_end <= self.window_start:
            raise ValueError(
                "ExtractedFeatureSet.window_end must be greater than window_start."
            )
        if set(self.domains.keys()) != set(self.sample_counts.keys()):
            raise ValueError(
                "ExtractedFeatureSet.sample_counts must have exactly the same "
                "keys as domains."
            )
        object.__setattr__(
            self,
            "domains",
            MappingProxyType({name: MappingProxyType(dict(values)) for name, values in self.domains.items()}),
        )
        object.__setattr__(self, "sample_counts", MappingProxyType(dict(self.sample_counts)))
