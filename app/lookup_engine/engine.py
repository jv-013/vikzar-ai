"""Read-only orchestration between validated runtime data and knowledge."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.knowledge_base.entities import (
    BiomechanicalReference,
    InjuryProfile,
    PlayerProfile,
    PositionProfile,
    ScientificSource,
)
from app.knowledge_base.repository import (
    KnowledgeBaseRepository,
    get_knowledge_base_repository,
)
from app.lookup_engine.entities import (
    EvidenceContext,
    InjuryProfileContext,
    LookupResult,
    MetricDefinition,
    MetricProvenanceContext,
    PlayerProfileContext,
    PositionProfileContext,
    ScientificSourceContext,
)
from app.lookup_engine.exceptions import (
    InjuryKnowledgeNotFoundError,
    KnowledgeReferenceNotFoundError,
    PositionKnowledgeNotFoundError,
)
from app.validation import ValidatedRawFeatureVector


logger = logging.getLogger("app.lookup_engine")


class LookupEngine:
    """Retrieve immutable scientific context for one validated RawFeatureVector.

    Parameters:
        knowledge_base: Read-only, startup-loaded repository injected by the
            application composition layer.

    Returns:
        A Lookup Engine instance that performs contextual retrieval only.

    Exceptions:
        None.
    """

    def __init__(self, knowledge_base: KnowledgeBaseRepository) -> None:
        self._knowledge_base = knowledge_base

    def lookup(self, feature_vector: ValidatedRawFeatureVector) -> LookupResult:
        """Retrieve contextual knowledge without changing validated ETL output.

        Parameters:
            feature_vector: RawFeatureVector already accepted by Validation.
                The Lookup Engine never parses or validates ETL input.

        Returns:
            Immutable LookupResult containing only Lookup Engine DTOs.

        Exceptions:
            PositionKnowledgeNotFoundError: Raised when the player's position
                is not configured in the Knowledge Base.
            InjuryKnowledgeNotFoundError: Raised when supplied injury context
                is not configured in the Knowledge Base.
            KnowledgeReferenceNotFoundError: Raised when configured knowledge
                refers to unavailable scientific metadata.
        """

        position_profile = self._get_position_profile(feature_vector)
        injury_profiles = self._get_injury_profiles(feature_vector)
        player_profile = self._knowledge_base.get_player_profile(
            feature_vector.player.player_id
        )
        references = self._get_metric_references(position_profile, injury_profiles)
        sources = self._get_sources(
            player_profile,
            position_profile,
            injury_profiles,
            references,
        )
        provenance = tuple(_to_provenance_context(reference) for reference in references)
        result = LookupResult(
            feature_vector_id=feature_vector.feature_vector_id,
            player_profile=_to_player_profile_context(player_profile),
            position_profile=_to_position_profile_context(position_profile),
            injury_profiles=tuple(
                _to_injury_profile_context(profile) for profile in injury_profiles
            ),
            metric_context=tuple(
                _to_metric_definition(reference, sources) for reference in references
            ),
            scientific_sources=tuple(_to_source_context(source) for source in sources),
            evidence=tuple(_to_evidence_context(source) for source in sources),
            provenance=provenance,
        )
        self._log_lookup(feature_vector, result)
        return result

    def _get_position_profile(
        self,
        feature_vector: ValidatedRawFeatureVector,
    ) -> PositionProfile:
        """Resolve the required football-position knowledge profile."""

        profile = self._knowledge_base.get_position_profile(feature_vector.player.position)
        if profile is None:
            self._log_lookup_failure(feature_vector, "position_profile")
            raise PositionKnowledgeNotFoundError(
                "No Knowledge Base position profile exists for the validated player position."
            )
        return profile

    def _get_injury_profiles(
        self,
        feature_vector: ValidatedRawFeatureVector,
    ) -> tuple[InjuryProfile, ...]:
        """Resolve supplied injury history and current status without inference."""

        profiles: list[InjuryProfile] = []
        resolved_keys: set[str] = set()
        for injury_context in (
            feature_vector.player.injury_history,
            feature_vector.player.injury_status,
        ):
            if injury_context is None or not injury_context.strip():
                continue
            profile = self._knowledge_base.get_injury_profile(injury_context)
            if profile is None:
                self._log_lookup_failure(feature_vector, "injury_profile")
                raise InjuryKnowledgeNotFoundError(
                    "No Knowledge Base injury profile exists for supplied injury context."
                )
            if profile.injury_key not in resolved_keys:
                profiles.append(profile)
                resolved_keys.add(profile.injury_key)
        return tuple(profiles)

    def _get_metric_references(
        self,
        position_profile: PositionProfile,
        injury_profiles: tuple[InjuryProfile, ...],
    ) -> tuple[BiomechanicalReference, ...]:
        """Resolve profile-declared metric definitions in deterministic order."""

        metric_keys: list[str] = list(position_profile.relevant_metric_keys)
        for injury_profile in injury_profiles:
            metric_keys.extend(injury_profile.relevant_metric_keys)

        references: list[BiomechanicalReference] = []
        resolved_keys: set[str] = set()
        for metric_key in metric_keys:
            if metric_key in resolved_keys:
                continue
            reference = self._knowledge_base.get_biomechanical_reference(metric_key)
            if reference is None:
                raise KnowledgeReferenceNotFoundError(
                    "Knowledge Base profile references unavailable biomechanical metadata."
                )
            references.append(reference)
            resolved_keys.add(metric_key)
        return tuple(references)

    def _get_sources(
        self,
        player_profile: PlayerProfile | None,
        position_profile: PositionProfile,
        injury_profiles: tuple[InjuryProfile, ...],
        references: tuple[BiomechanicalReference, ...],
    ) -> tuple[ScientificSource, ...]:
        """Resolve all source records referenced by retrieved context."""

        source_ids: list[str] = []
        if player_profile is not None:
            source_ids.extend(player_profile.source_ids)
        source_ids.extend(position_profile.source_ids)
        for injury_profile in injury_profiles:
            source_ids.extend(injury_profile.source_ids)
        for reference in references:
            source_ids.extend(reference.source_ids)

        sources: list[ScientificSource] = []
        resolved_ids: set[str] = set()
        for source_id in source_ids:
            if source_id in resolved_ids:
                continue
            source = self._knowledge_base.get_scientific_source(source_id)
            if source is None:
                raise KnowledgeReferenceNotFoundError(
                    "Knowledge context references unavailable scientific-source metadata."
                )
            sources.append(source)
            resolved_ids.add(source_id)
        return tuple(sources)

    @staticmethod
    def _log_lookup(
        feature_vector: ValidatedRawFeatureVector,
        result: LookupResult,
    ) -> None:
        """Log successful lookup using structured, non-clinical metadata only."""

        logger.info(
            "Contextual knowledge lookup completed.",
            extra={
                "component": "lookup_engine",
                "feature_vector_id": feature_vector.feature_vector_id,
                "player_id": feature_vector.player.player_id,
                "metric_context_count": len(result.metric_context),
                "injury_context_count": len(result.injury_profiles),
                "scientific_source_count": len(result.scientific_sources),
            },
        )

    @staticmethod
    def _log_lookup_failure(
        feature_vector: ValidatedRawFeatureVector,
        lookup_type: str,
    ) -> None:
        """Log expected unresolved contextual knowledge without source values."""

        logger.warning(
            "Contextual knowledge lookup failed.",
            extra={
                "component": "lookup_engine",
                "feature_vector_id": feature_vector.feature_vector_id,
                "player_id": feature_vector.player.player_id,
                "lookup_type": lookup_type,
            },
        )


@lru_cache(maxsize=1)
def get_lookup_engine() -> LookupEngine:
    """Return the process-wide Lookup Engine for application startup injection.

    Parameters:
        None.

    Returns:
        Cached LookupEngine using the cached read-only Knowledge Base repository.

    Exceptions:
        app.knowledge_base.exceptions.KnowledgeBaseDataError: Raised when the
            Knowledge Base cannot initialize on first access.
    """

    return LookupEngine(get_knowledge_base_repository())


def _to_player_profile_context(
    profile: PlayerProfile | None,
) -> PlayerProfileContext | None:
    """Copy an internal player profile into the public Lookup Engine DTO."""

    if profile is None:
        return None
    return PlayerProfileContext(
        player_id=profile.player_id,
        profile_version=profile.profile_version,
        approved_baseline_reference_keys=profile.approved_baseline_reference_keys,
        source_ids=profile.source_ids,
    )


def _to_position_profile_context(profile: PositionProfile) -> PositionProfileContext:
    """Copy an internal position profile into the public Lookup Engine DTO."""

    return PositionProfileContext(
        position_key=profile.position_key,
        display_name=profile.display_name,
        movement_demands=profile.movement_demands,
        interpretation_note=profile.interpretation_note,
        source_ids=profile.source_ids,
    )


def _to_injury_profile_context(profile: InjuryProfile) -> InjuryProfileContext:
    """Copy an internal injury profile into the public Lookup Engine DTO."""

    return InjuryProfileContext(
        injury_key=profile.injury_key,
        display_name=profile.display_name,
        interpretation_note=profile.interpretation_note,
        source_ids=profile.source_ids,
    )


def _to_provenance_context(
    reference: BiomechanicalReference,
) -> MetricProvenanceContext:
    """Copy scientific measurement provenance into a public result DTO."""

    provenance = reference.provenance
    return MetricProvenanceContext(
        metric_name=reference.metric_key,
        category=provenance.category,
        measured_by=provenance.hardware_sources,
        measurable_feature_paths=provenance.measurable_feature_paths,
        scientific_basis=provenance.scientific_basis,
    )


def _to_metric_definition(
    reference: BiomechanicalReference,
    sources: tuple[ScientificSource, ...],
) -> MetricDefinition:
    """Create self-describing metric metadata from read-only knowledge."""

    source_by_id = {source.source_id: source for source in sources}
    source_records = tuple(source_by_id[source_id] for source_id in reference.source_ids)
    provenance = _to_provenance_context(reference)
    return MetricDefinition(
        name=reference.metric_key,
        description=reference.display_name,
        measured_by=provenance.measured_by,
        scientific_source_ids=reference.source_ids,
        evidence_levels=tuple(source.evidence_level for source in source_records),
        reference_information=reference.interpretation_note,
        provenance=provenance,
    )


def _to_source_context(source: ScientificSource) -> ScientificSourceContext:
    """Copy an internal scientific source into a public Lookup Engine DTO."""

    return ScientificSourceContext(
        source_id=source.source_id,
        title=source.title,
        publication_year=source.publication_year,
        publisher=source.publisher,
        persistent_identifier=source.persistent_identifier,
        evidence_level=source.evidence_level,
        review_status=source.review_status,
    )


def _to_evidence_context(source: ScientificSource) -> EvidenceContext:
    """Copy source evidence classification into a public Lookup Engine DTO."""

    return EvidenceContext(
        source_id=source.source_id,
        evidence_level=source.evidence_level,
        review_status=source.review_status,
    )
