"""Immutable public result contracts owned by the Lookup Engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


MetricCategory = Literal[
    "hardware_measured",
    "mathematically_derived",
    "ai_estimated",
]
SensorType = Literal["imu", "fsr", "emg"]
EvidenceLevel = Literal["high", "moderate"]
ReviewStatus = Literal["reference_verified"]


class ImmutableLookupModel(BaseModel):
    """Base model that prevents callers from mutating lookup output."""

    class Config:
        """Pydantic configuration compatible with supported Pydantic versions."""

        extra = "forbid"
        frozen = True


class PlayerProfileContext(ImmutableLookupModel):
    """Read-only approved player-profile context without baseline values.

    Parameters:
        player_id: Stable player identifier associated with the approved profile.
        profile_version: Governed player-profile version.
        approved_baseline_reference_keys: Declared baseline references, if any.
        source_ids: Scientific or governed source identifiers backing the profile.

    Returns:
        Immutable player-profile context owned by the Lookup Engine.

    Exceptions:
        pydantic.ValidationError: Raised when context data is malformed.
    """

    player_id: str
    profile_version: str
    approved_baseline_reference_keys: tuple[str, ...]
    source_ids: tuple[str, ...]


class PositionProfileContext(ImmutableLookupModel):
    """Read-only football-position context for downstream feature enhancement."""

    position_key: str
    display_name: str
    movement_demands: tuple[str, ...]
    interpretation_note: str
    source_ids: tuple[str, ...]


class InjuryProfileContext(ImmutableLookupModel):
    """Read-only, non-diagnostic injury-history context."""

    injury_key: str
    display_name: str
    interpretation_note: str
    source_ids: tuple[str, ...]


class ScientificSourceContext(ImmutableLookupModel):
    """Verifiable scientific-source summary exposed by the Lookup Engine."""

    source_id: str
    title: str
    publication_year: int
    publisher: str
    persistent_identifier: str
    evidence_level: EvidenceLevel
    review_status: ReviewStatus


class EvidenceContext(ImmutableLookupModel):
    """Evidence classification for a source used in the current lookup."""

    source_id: str
    evidence_level: EvidenceLevel
    review_status: ReviewStatus


class MetricProvenanceContext(ImmutableLookupModel):
    """Measurement lineage for one returned scientific metric definition."""

    metric_name: str
    category: MetricCategory
    measured_by: tuple[SensorType, ...]
    measurable_feature_paths: tuple[str, ...]
    scientific_basis: str


class MetricDefinition(ImmutableLookupModel):
    """Self-describing metric context with no sensor-value interpretation.

    Parameters:
        name: Stable knowledge-base metric identifier.
        description: Human-readable metric name.
        measured_by: Hardware systems contributing measurable source data.
        scientific_source_ids: Source records supporting the definition.
        evidence_levels: Evidence classifications for linked source records.
        units: Validated unit when declared by the Knowledge Base; None otherwise.
        reference_information: Scientific interpretation metadata, never a
            fabricated reference range.
        provenance: Measurement lineage of the metric.

    Returns:
        Immutable metric metadata for downstream AI modules.

    Exceptions:
        pydantic.ValidationError: Raised when metric context is malformed.
    """

    name: str
    description: str
    measured_by: tuple[SensorType, ...]
    scientific_source_ids: tuple[str, ...]
    evidence_levels: tuple[EvidenceLevel, ...]
    units: str | None = None
    reference_information: str
    provenance: MetricProvenanceContext


class LookupResult(ImmutableLookupModel):
    """Complete immutable contextual output of one Lookup Engine operation.

    This is the only public output produced by the Lookup Engine. It contains
    copied contextual data rather than Knowledge Base repository entities.
    """

    feature_vector_id: str
    player_profile: PlayerProfileContext | None = None
    position_profile: PositionProfileContext
    injury_profiles: tuple[InjuryProfileContext, ...]
    metric_context: tuple[MetricDefinition, ...]
    scientific_sources: tuple[ScientificSourceContext, ...]
    evidence: tuple[EvidenceContext, ...]
    provenance: tuple[MetricProvenanceContext, ...]
