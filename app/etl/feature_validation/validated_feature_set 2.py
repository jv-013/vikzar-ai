"""
ValidatedFeatureSet: the internal contract between Feature Validation
and Publisher.

ValidatedFeatureSet is an ETL-internal type only, like RawPacket,
ValidatedPacket, SynchronizedFrame, CalibratedFrame, FilteredFrame,
Window, and ExtractedFeatureSet. It must never be imported outside
app/etl and has no relationship to RawFeatureVector or
EnhancedFeatureVector — that boundary crossing happens later, in
app/etl/publisher.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from app.etl.feature_extraction import ExtractedFeatureSet

from .quality import BiomarkerQuality, SetQualityObservation


@dataclass(frozen=True)
class ValidatedFeatureSet:
    """
    One ExtractedFeatureSet, annotated with an explicit quality
    assessment for every biomarker it contains.

    Purpose
        Answer "can these extracted biomechanical biomarkers be
        trusted?" without ever assigning them meaning. Wraps the
        original ExtractedFeatureSet completely unchanged — Feature
        Validation never modifies, deletes, replaces, or interpolates a
        value (Founder Decision 7). Every biomarker present in
        raw.domains survives into biomarker_quality with an explicit
        status, never silently dropped (Founder Decision 2).

    Why wrap rather than re-declare
        raw carries group_id/window_specification_name/window_start/
        window_end/domains/sample_counts. Re-declaring them here would
        duplicate both the original values and the risk of the two
        copies drifting apart. biomarker_quality is purely additive
        metadata, keyed identically to raw.domains.

    Attributes
        raw: The complete, unmodified ExtractedFeatureSet this
            validation was performed on.
        biomarker_quality: BiomarkerQuality per biomarker, keyed
            exactly like raw.domains (domain -> feature_name ->
            BiomarkerQuality). Every key present in raw.domains has a
            corresponding entry here; no key exists here that isn't in
            raw.domains.
        set_observations: Findings not tied to one specific present
            biomarker (e.g. an entire expected domain being absent).

    Raises
        ValueError: If biomarker_quality's keys do not exactly match
            raw.domains' keys, at both the domain and feature-name
            level.
    """

    raw: ExtractedFeatureSet
    biomarker_quality: Mapping[str, Mapping[str, BiomarkerQuality]]
    set_observations: Sequence[SetQualityObservation]

    def __post_init__(self) -> None:
        if set(self.biomarker_quality.keys()) != set(self.raw.domains.keys()):
            raise ValueError(
                "ValidatedFeatureSet.biomarker_quality must have exactly the "
                "same domain keys as raw.domains."
            )
        for domain_name, features in self.raw.domains.items():
            if set(self.biomarker_quality[domain_name].keys()) != set(features.keys()):
                raise ValueError(
                    f"ValidatedFeatureSet.biomarker_quality[{domain_name!r}] must "
                    f"have exactly the same feature-name keys as "
                    f"raw.domains[{domain_name!r}]."
                )
        object.__setattr__(
            self,
            "biomarker_quality",
            MappingProxyType(
                {name: MappingProxyType(dict(values)) for name, values in self.biomarker_quality.items()}
            ),
        )
        object.__setattr__(self, "set_observations", tuple(self.set_observations))
