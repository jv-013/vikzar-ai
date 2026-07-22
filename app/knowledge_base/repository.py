"""Read-only repository for validated Vikzar AI domain knowledge."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, TypeVar

from pydantic import BaseModel, ValidationError

from app.config.knowledge_base_config import (
    BIOMECHANICAL_REFERENCES_FILENAME,
    INJURY_PROFILES_FILENAME,
    KNOWLEDGE_BASE_DATA_DIRECTORY,
    KNOWLEDGE_BASE_SCHEMA_VERSION,
    KNOWLEDGE_METADATA_FILENAME,
    PLAYER_PROFILES_FILENAME,
    POSITION_PROFILES_FILENAME,
)
from app.knowledge_base.entities import (
    BiomechanicalReference,
    BiomechanicalReferencesDocument,
    InjuryProfile,
    InjuryProfilesDocument,
    KnowledgeMetadata,
    PlayerProfile,
    PlayerProfilesDocument,
    PositionProfile,
    PositionProfilesDocument,
    ScientificSource,
)
from app.knowledge_base.exceptions import KnowledgeBaseDataError


logger = logging.getLogger("app.knowledge_base")
ModelType = TypeVar("ModelType", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class KnowledgeBaseSnapshot:
    """Immutable in-memory index of all validated knowledge documents."""

    player_profiles: Mapping[str, PlayerProfile]
    position_profiles: Mapping[str, PositionProfile]
    injury_profiles: Mapping[str, InjuryProfile]
    biomechanical_references: Mapping[str, BiomechanicalReference]
    scientific_sources: Mapping[str, ScientificSource]
    metadata: KnowledgeMetadata


class KnowledgeBaseRepository:
    """Load and query scientifically validated, read-only knowledge data.

    Parameters:
        data_directory: Directory containing the four packaged JSON documents.
            Defaults to the application configuration location.

    Returns:
        A repository with immutable, indexed knowledge available for lookups.

    Exceptions:
        KnowledgeBaseDataError: Raised when a knowledge document is missing,
            malformed, incompatible, or internally inconsistent.
    """

    def __init__(self, data_directory: Path | None = None) -> None:
        self._data_directory = data_directory or KNOWLEDGE_BASE_DATA_DIRECTORY
        self._snapshot = self._load_snapshot()

    def get_player_profile(self, player_id: str) -> PlayerProfile | None:
        """Retrieve approved player-specific baseline metadata.

        Parameters:
            player_id: Stable player identifier from the FeatureVector.

        Returns:
            The immutable profile, or None when no approved profile exists.

        Exceptions:
            None.
        """

        return self._lookup(self._snapshot.player_profiles, player_id, "player_profile")

    def get_position_profile(self, position: str) -> PositionProfile | None:
        """Retrieve football-role context using a canonical name or alias.

        Parameters:
            position: Player position supplied by the FeatureVector.

        Returns:
            The immutable position profile, or None when not configured.

        Exceptions:
            None.
        """

        return self._lookup(self._snapshot.position_profiles, position, "position_profile")

    def get_injury_profile(self, injury_context: str | None) -> InjuryProfile | None:
        """Retrieve non-diagnostic historical injury context.

        Parameters:
            injury_context: Approved injury-history or current-status descriptor.

        Returns:
            The immutable injury profile, or None for missing or unknown context.

        Exceptions:
            None.
        """

        if injury_context is None:
            return None
        return self._lookup(self._snapshot.injury_profiles, injury_context, "injury_profile")

    def get_biomechanical_reference(
        self,
        metric_key: str,
    ) -> BiomechanicalReference | None:
        """Retrieve scientific provenance and interpretation for a metric.

        Parameters:
            metric_key: Canonical metric identifier.

        Returns:
            The immutable metric reference, or None when not registered.

        Exceptions:
            None.
        """

        return self._lookup(
            self._snapshot.biomechanical_references,
            metric_key,
            "biomechanical_reference",
        )

    def get_scientific_source(self, source_id: str) -> ScientificSource | None:
        """Retrieve a source record supporting one or more knowledge entries.

        Parameters:
            source_id: Stable source identifier declared in knowledge metadata.

        Returns:
            The immutable scientific-source record, or None when unknown.

        Exceptions:
            None.
        """

        return self._lookup(self._snapshot.scientific_sources, source_id, "scientific_source")

    def get_metadata(self) -> KnowledgeMetadata:
        """Retrieve immutable release metadata for the loaded knowledge snapshot.

        Parameters:
            None.

        Returns:
            Version and source registry metadata for the loaded release.

        Exceptions:
            None.
        """

        return self._snapshot.metadata

    def _load_snapshot(self) -> KnowledgeBaseSnapshot:
        """Load, parse, and cross-validate every required knowledge document.

        Parameters:
            None.

        Returns:
            Immutable indexed knowledge snapshot.

        Exceptions:
            KnowledgeBaseDataError: Raised when packaged knowledge is invalid.
        """

        metadata = self._load_document(KNOWLEDGE_METADATA_FILENAME, KnowledgeMetadata)
        player_document = self._load_document(
            PLAYER_PROFILES_FILENAME,
            PlayerProfilesDocument,
        )
        position_document = self._load_document(
            POSITION_PROFILES_FILENAME,
            PositionProfilesDocument,
        )
        injury_document = self._load_document(
            INJURY_PROFILES_FILENAME,
            InjuryProfilesDocument,
        )
        reference_document = self._load_document(
            BIOMECHANICAL_REFERENCES_FILENAME,
            BiomechanicalReferencesDocument,
        )

        references = self._index_by_key(
            reference_document.references,
            "metric_key",
            "biomechanical reference",
        )
        sources = self._index_by_key(
            metadata.scientific_sources,
            "source_id",
            "scientific source",
        )
        self._validate_referenced_metrics(
            position_document.profiles,
            injury_document.profiles,
            references,
        )
        self._validate_source_references(
            (*player_document.profiles, *position_document.profiles, *injury_document.profiles, *reference_document.references),
            sources,
        )
        snapshot = KnowledgeBaseSnapshot(
            player_profiles=MappingProxyType(
                self._index_by_key(player_document.profiles, "player_id", "player profile")
            ),
            position_profiles=MappingProxyType(
                self._index_with_aliases(
                    position_document.profiles,
                    "position_key",
                    "position profile",
                )
            ),
            injury_profiles=MappingProxyType(
                self._index_with_aliases(
                    injury_document.profiles,
                    "injury_key",
                    "injury profile",
                )
            ),
            biomechanical_references=MappingProxyType(references),
            scientific_sources=MappingProxyType(sources),
            metadata=metadata,
        )
        category_counts = {
            category: sum(
                reference.provenance.category == category
                for reference in snapshot.biomechanical_references.values()
            )
            for category in ("hardware_measured", "mathematically_derived", "ai_estimated")
        }
        logger.info(
            "Knowledge base initialized.",
            extra={
                "component": "knowledge_base",
                "data_directory": str(self._data_directory),
                "knowledge_version": metadata.knowledge_version,
                "generated_on": metadata.generated_on.isoformat(),
                "knowledge_entry_count": (
                    len(player_document.profiles)
                    + len(position_document.profiles)
                    + len(injury_document.profiles)
                    + len(snapshot.biomechanical_references)
                ),
                "scientific_source_count": metadata.scientific_source_count,
                "player_profile_count": len(snapshot.player_profiles),
                "position_profile_count": len(position_document.profiles),
                "injury_profile_count": len(injury_document.profiles),
                "biomechanical_reference_count": len(snapshot.biomechanical_references),
                "hardware_measured_reference_count": category_counts["hardware_measured"],
                "mathematically_derived_reference_count": category_counts["mathematically_derived"],
                "ai_estimated_reference_count": category_counts["ai_estimated"],
            },
        )
        return snapshot

    def _load_document(self, filename: str, model_type: type[ModelType]) -> ModelType:
        """Read and validate one versioned JSON knowledge document.

        Parameters:
            filename: Configured JSON filename.
            model_type: Immutable Pydantic document contract.

        Returns:
            Validated document model.

        Exceptions:
            KnowledgeBaseDataError: Raised when file access or validation fails.
        """

        path = self._data_directory / filename
        try:
            with path.open(encoding="utf-8") as data_file:
                payload: Any = json.load(data_file)
        except FileNotFoundError as exc:
            raise KnowledgeBaseDataError(f"Knowledge document is missing: {path}") from exc
        except json.JSONDecodeError as exc:
            raise KnowledgeBaseDataError(f"Knowledge document contains invalid JSON: {path}") from exc
        except OSError as exc:
            raise KnowledgeBaseDataError(f"Knowledge document cannot be read: {path}") from exc

        try:
            document = _validate_model(model_type, payload)
        except ValidationError as exc:
            raise KnowledgeBaseDataError(f"Knowledge document failed validation: {path}") from exc

        if document.schema_version != KNOWLEDGE_BASE_SCHEMA_VERSION:
            raise KnowledgeBaseDataError(
                f"Knowledge document has unsupported schema version: {path}"
            )
        return document

    @staticmethod
    def _index_by_key(
        entries: tuple[Any, ...],
        key_attribute: str,
        entity_name: str,
    ) -> dict[str, Any]:
        """Index entities by canonical key while rejecting ambiguous data."""

        index: dict[str, Any] = {}
        for entry in entries:
            key = _normalise_lookup_key(getattr(entry, key_attribute))
            if not key:
                raise KnowledgeBaseDataError(f"{entity_name.capitalize()} key cannot be blank.")
            if key in index:
                raise KnowledgeBaseDataError(
                    f"Duplicate {entity_name} key in knowledge data: {key}"
                )
            index[key] = entry
        return index

    @classmethod
    def _index_with_aliases(
        cls,
        entries: tuple[Any, ...],
        key_attribute: str,
        entity_name: str,
    ) -> dict[str, Any]:
        """Index canonical keys and aliases while rejecting collisions."""

        index: dict[str, Any] = {}
        for entry in entries:
            values = (getattr(entry, key_attribute), *entry.aliases)
            for value in values:
                key = _normalise_lookup_key(value)
                if not key:
                    raise KnowledgeBaseDataError(
                        f"{entity_name.capitalize()} alias cannot be blank."
                    )
                if key in index:
                    raise KnowledgeBaseDataError(
                        f"Duplicate {entity_name} key or alias in knowledge data: {key}"
                    )
                index[key] = entry
        return index

    @staticmethod
    def _validate_referenced_metrics(
        position_profiles: tuple[PositionProfile, ...],
        injury_profiles: tuple[InjuryProfile, ...],
        references: Mapping[str, BiomechanicalReference],
    ) -> None:
        """Ensure all contextual profiles reference defined metrics only."""

        for profile in (*position_profiles, *injury_profiles):
            for metric_key in profile.relevant_metric_keys:
                if _normalise_lookup_key(metric_key) not in references:
                    raise KnowledgeBaseDataError(
                        "Knowledge profile references an unknown biomechanical metric: "
                        f"{metric_key}"
                    )

    @staticmethod
    def _validate_source_references(
        entries: tuple[Any, ...],
        sources: Mapping[str, ScientificSource],
    ) -> None:
        """Ensure every knowledge entry has registered, unique source links."""

        for entry in entries:
            if not entry.source_ids:
                raise KnowledgeBaseDataError("Knowledge entry must declare at least one source.")
            normalized_source_ids = tuple(
                _normalise_lookup_key(source_id) for source_id in entry.source_ids
            )
            if len(set(normalized_source_ids)) != len(normalized_source_ids):
                raise KnowledgeBaseDataError("Knowledge entry contains duplicate source identifiers.")
            for source_id in normalized_source_ids:
                if source_id not in sources:
                    raise KnowledgeBaseDataError(
                        f"Knowledge entry references an unknown scientific source: {source_id}"
                    )

    @staticmethod
    def _lookup(
        index: Mapping[str, ModelType],
        value: str,
        lookup_type: str,
    ) -> ModelType | None:
        """Return an immutable entity and log only lookup metadata."""

        key = _normalise_lookup_key(value)
        result = index.get(key)
        logger.debug(
            "Knowledge base lookup completed.",
            extra={
                "component": "knowledge_base",
                "lookup_type": lookup_type,
                "found": result is not None,
            },
        )
        return result


def _validate_model(model_type: type[ModelType], payload: Any) -> ModelType:
    """Validate a Pydantic model across supported Pydantic versions."""

    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)  # type: ignore[attr-defined, no-any-return]
    return model_type.parse_obj(payload)  # type: ignore[no-any-return]


def _normalise_lookup_key(value: str) -> str:
    """Normalize externally supplied human-readable lookup values."""

    return "_".join(value.strip().casefold().replace("-", " ").split())


@lru_cache(maxsize=1)
def get_knowledge_base_repository() -> KnowledgeBaseRepository:
    """Return the process-wide, startup-loadable knowledge-base repository.

    The cached instance ensures production lookup paths use the validated
    in-memory snapshot instead of re-reading JSON per request. Application
    startup code may call this function eagerly and inject the resulting
    repository into the Lookup Engine.

    Parameters:
        None.

    Returns:
        One immutable KnowledgeBaseRepository instance per application process.

    Exceptions:
        KnowledgeBaseDataError: Raised when packaged knowledge cannot be loaded
            or validated during first initialization.
    """

    return KnowledgeBaseRepository()
