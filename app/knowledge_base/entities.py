"""Immutable entities and JSON document contracts for domain knowledge."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, root_validator


MetricCategory = Literal[
    "hardware_measured",
    "mathematically_derived",
    "ai_estimated",
]
SensorType = Literal["imu", "fsr", "emg"]
SourceType = Literal[
    "systematic_review",
    "peer_reviewed_study",
    "technical_guideline",
]
EvidenceLevel = Literal["high", "moderate"]
ReviewStatus = Literal["reference_verified"]


class ImmutableKnowledgeModel(BaseModel):
    """Base model that prevents runtime mutation of knowledge entities."""

    class Config:
        """Pydantic configuration compatible with supported Pydantic versions."""

        extra = "forbid"
        frozen = True


class MetricProvenance(ImmutableKnowledgeModel):
    """Scientific provenance for one knowledge-base metric.

    Parameters:
        category: The sole permitted origin category for the metric.
        hardware_sources: Sensors that directly observe the source signal.
        measurable_feature_paths: Raw or derived measurable inputs supporting
            the metric.
        scientific_basis: Concise explanation of the measurement relationship.

    Returns:
        An immutable, validated metric provenance record.

    Exceptions:
        pydantic.ValidationError: Raised when provenance is incomplete or
            contradicts the declared metric category.
    """

    category: MetricCategory
    hardware_sources: tuple[SensorType, ...] = Field(default_factory=tuple)
    measurable_feature_paths: tuple[str, ...] = Field(default_factory=tuple)
    scientific_basis: str

    @root_validator(skip_on_failure=True)
    def validate_measurement_chain(cls, values: dict[str, object]) -> dict[str, object]:
        """Require an auditable path from each metric to measurable data.

        Parameters:
            values: Parsed model values.

        Returns:
            Validated model values.

        Exceptions:
            ValueError: Raised when the provenance does not meet scientific
                traceability requirements.
        """

        category = values.get("category")
        hardware_sources = values.get("hardware_sources", ())
        feature_paths = values.get("measurable_feature_paths", ())
        scientific_basis = values.get("scientific_basis", "")

        if not str(scientific_basis).strip():
            raise ValueError("scientific_basis must be a non-empty explanation.")
        if category == "hardware_measured" and not hardware_sources:
            raise ValueError("Hardware-measured metrics require hardware_sources.")
        if category in {"mathematically_derived", "ai_estimated"} and not feature_paths:
            raise ValueError(
                "Derived and AI-estimated metrics require measurable_feature_paths."
            )
        return values


class ScientificSource(ImmutableKnowledgeModel):
    """Verifiable scientific or technical source supporting domain knowledge.

    Parameters:
        source_id: Stable identifier used by knowledge entries.
        title: Published work or guideline title.
        publication_year: Year in which the source was published.
        publisher: Responsible journal, organization, or publisher.
        source_type: Evidence publication or technical-guideline classification.
        persistent_identifier: DOI or stable source URL.
        evidence_level: Curated strength classification for intended use.
        review_status: Curation status for the reference record.

    Returns:
        An immutable, traceable scientific-source record.

    Exceptions:
        pydantic.ValidationError: Raised when the source record is malformed.
    """

    source_id: str
    title: str
    publication_year: int
    publisher: str
    source_type: SourceType
    persistent_identifier: str
    evidence_level: EvidenceLevel
    review_status: ReviewStatus

    @root_validator(skip_on_failure=True)
    def validate_required_text(cls, values: dict[str, object]) -> dict[str, object]:
        """Reject empty source identity and citation fields.

        Parameters:
            values: Parsed model values.

        Returns:
            Validated model values.

        Exceptions:
            ValueError: Raised when a required citation field is blank.
        """

        for field_name in (
            "source_id",
            "title",
            "publisher",
            "persistent_identifier",
        ):
            if not str(values.get(field_name, "")).strip():
                raise ValueError(f"{field_name} must be a non-empty string.")
        return values


class KnowledgeMetadata(ImmutableKnowledgeModel):
    """Versioned release metadata and source registry for packaged knowledge."""

    schema_version: str
    knowledge_version: str
    generated_on: date
    scientific_source_count: int
    scientific_sources: tuple[ScientificSource, ...]

    @root_validator(skip_on_failure=True)
    def validate_source_count(cls, values: dict[str, object]) -> dict[str, object]:
        """Ensure release metadata cannot misstate its source inventory."""

        declared_count = values.get("scientific_source_count")
        sources = values.get("scientific_sources", ())
        if declared_count != len(sources):
            raise ValueError("scientific_source_count must equal the source registry size.")
        return values


class PlayerProfile(ImmutableKnowledgeModel):
    """Optional, approved player-specific baseline metadata.

    Numeric player baselines are intentionally absent until collected through
    the governed calibration workflow; this prevents fabricated personalization.
    """

    player_id: str
    profile_version: str
    approved_baseline_reference_keys: tuple[str, ...] = Field(default_factory=tuple)
    source_ids: tuple[str, ...]


class PositionProfile(ImmutableKnowledgeModel):
    """Football-role context represented without prescriptive thresholds."""

    position_key: str
    display_name: str
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    movement_demands: tuple[str, ...]
    relevant_metric_keys: tuple[str, ...]
    interpretation_note: str
    source_ids: tuple[str, ...]


class InjuryProfile(ImmutableKnowledgeModel):
    """Non-diagnostic injury-history context for scientific interpretation."""

    injury_key: str
    display_name: str
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    relevant_metric_keys: tuple[str, ...]
    interpretation_note: str
    source_ids: tuple[str, ...]


class BiomechanicalReference(ImmutableKnowledgeModel):
    """Definition of a scientifically traceable biomechanics metric."""

    metric_key: str
    display_name: str
    provenance: MetricProvenance
    movement_contexts: tuple[str, ...]
    interpretation_note: str
    source_ids: tuple[str, ...]


class PlayerProfilesDocument(ImmutableKnowledgeModel):
    """JSON document contract for approved player profiles."""

    schema_version: str
    profiles: tuple[PlayerProfile, ...] = Field(default_factory=tuple)


class PositionProfilesDocument(ImmutableKnowledgeModel):
    """JSON document contract for football position profiles."""

    schema_version: str
    profiles: tuple[PositionProfile, ...]


class InjuryProfilesDocument(ImmutableKnowledgeModel):
    """JSON document contract for injury-history profiles."""

    schema_version: str
    profiles: tuple[InjuryProfile, ...]


class BiomechanicalReferencesDocument(ImmutableKnowledgeModel):
    """JSON document contract for biomechanical references."""

    schema_version: str
    references: tuple[BiomechanicalReference, ...]
