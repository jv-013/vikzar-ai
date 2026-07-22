"""Build leakage-safe supervised examples from verified measured sessions."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.config import dataset_builder_config
from app.ground_truth.contracts import AlignedTrainingWindow, VerifiedSynchronizedTrainingSession

from .contracts import (
    ChecksumEntry,
    DatasetBuildSpec,
    DatasetFeatureSchema,
    DatasetSource,
    DatasetSplitMembership,
    NumericValue,
    TrainingExample,
    VersionedTrainingDataset,
)
from .exceptions import DatasetInputError
from .splitter import GroupedDatasetSplitter


@dataclass(frozen=True)
class DatasetBuildResult:
    """In-memory result ready for atomic versioned-dataset persistence."""

    dataset: VersionedTrainingDataset
    examples: tuple[TrainingExample, ...]


@dataclass(frozen=True)
class _CandidateExample:
    """Internal example before its player/session split assignment."""

    verified_session_id: str
    capture_session_id: str
    player_id: str
    session_id: str
    group_id: str
    source_feature_vector_id: str
    aligned_window_id: str
    features: tuple[NumericValue, ...]
    targets: tuple[NumericValue, ...]


class DatasetBuilder:
    """Transform only accepted measured Phase 2 sessions into supervised data."""

    def __init__(
        self,
        splitter: GroupedDatasetSplitter | None = None,
    ) -> None:
        self._splitter = splitter or GroupedDatasetSplitter()

    def build(
        self,
        sessions: Iterable[VerifiedSynchronizedTrainingSession],
        spec: DatasetBuildSpec,
    ) -> DatasetBuildResult:
        """Build one deterministic dataset from immutable verified sessions.

        No feature is inferred or imputed. Every accepted aligned window must
        provide an identical Smart Pod feature schema and every requested
        direct-measurement target exactly once.
        """

        ordered_sessions = tuple(sorted(sessions, key=lambda session: session.verified_session_id))
        if not ordered_sessions:
            raise DatasetInputError("At least one verified session is required to build a dataset.")
        if len({session.verified_session_id for session in ordered_sessions}) != len(ordered_sessions):
            raise DatasetInputError("Verified session IDs must be unique within one dataset build.")

        candidates: list[_CandidateExample] = []
        sources: list[DatasetSource] = []
        feature_names: tuple[str, ...] | None = None
        example_keys: set[str] = set()
        for session in ordered_sessions:
            sources.append(self._source_for(session))
            labels_by_window = self._labels_by_window(session, spec)
            for window in sorted(session.aligned_windows, key=lambda item: item.aligned_window_id):
                features = self._features_for(window, spec)
                names = tuple(item.name for item in features)
                if feature_names is None:
                    feature_names = names
                elif names != feature_names:
                    raise DatasetInputError(
                        "All accepted windows must share the same Smart Pod feature schema."
                    )
                targets = labels_by_window.get((window.aligned_window_id, window.group_id))
                if targets is None:
                    raise DatasetInputError(
                        "Accepted aligned window is missing a requested measured EMG target."
                    )
                example_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"dataset-example:{session.verified_session_id}:{window.aligned_window_id}",
                    )
                )
                if example_id in example_keys:
                    raise DatasetInputError("Dataset example IDs must be unique.")
                example_keys.add(example_id)
                candidates.append(
                    _CandidateExample(
                        verified_session_id=session.verified_session_id,
                        capture_session_id=session.capture_session_id,
                        player_id=session.player_id,
                        session_id=session.session_id,
                        group_id=window.group_id,
                        source_feature_vector_id=window.source_feature_vector_id,
                        aligned_window_id=window.aligned_window_id,
                        features=features,
                        targets=targets,
                    )
                )
        if not candidates or feature_names is None:
            raise DatasetInputError("No accepted labeled windows are available for dataset construction.")

        assignment = self._splitter.assign(
            {(candidate.player_id, candidate.session_id) for candidate in candidates},
            spec.split_policy,
        )
        examples = tuple(
            TrainingExample(
                example_id=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"dataset-example:{candidate.verified_session_id}:{candidate.aligned_window_id}",
                    )
                ),
                verified_session_id=candidate.verified_session_id,
                capture_session_id=candidate.capture_session_id,
                player_id=candidate.player_id,
                session_id=candidate.session_id,
                group_id=candidate.group_id,
                source_feature_vector_id=candidate.source_feature_vector_id,
                aligned_window_id=candidate.aligned_window_id,
                split=assignment[(candidate.player_id, candidate.session_id)],
                features=candidate.features,
                targets=candidate.targets,
            )
            for candidate in candidates
        )
        target_names = tuple(f"target__{name}" for name in spec.target_metric_names)
        dataset = VersionedTrainingDataset(
            dataset_id=self._dataset_id(spec, sources),
            schema_version=dataset_builder_config.DATASET_BUILDER_SCHEMA_VERSION,
            created_at=max(session.provenance.generated_at for session in ordered_sessions),
            build_spec=spec,
            feature_schema=DatasetFeatureSchema(feature_names=feature_names, target_names=target_names),
            sources=tuple(sources),
            split_memberships=tuple(
                DatasetSplitMembership(player_id=player_id, session_id=session_id, split=split)
                for (player_id, session_id), split in sorted(assignment.items())
            ),
            example_count=len(examples),
        )
        return DatasetBuildResult(dataset=dataset, examples=examples)

    @staticmethod
    def _source_for(session: VerifiedSynchronizedTrainingSession) -> DatasetSource:
        hashes: list[ChecksumEntry] = []
        for name, value in sorted(session.provenance.source_sha256.items()):
            hashes.append(ChecksumEntry(name=name, sha256=value))
        return DatasetSource(
            verified_session_id=session.verified_session_id,
            capture_session_id=session.capture_session_id,
            player_id=session.player_id,
            session_id=session.session_id,
            source_sha256=tuple(hashes),
        )

    @staticmethod
    def _labels_by_window(
        session: VerifiedSynchronizedTrainingSession,
        spec: DatasetBuildSpec,
    ) -> dict[tuple[str, str], tuple[NumericValue, ...]]:
        """Collect required direct measured labels with strict cardinality checks."""

        requested = set(spec.target_metric_names)
        windows_by_key = {
            (window.aligned_window_id, window.group_id): window
            for window in session.aligned_windows
        }
        values: dict[tuple[str, str], dict[str, float]] = {}
        for label in session.labels:
            if label.metric_name not in requested:
                continue
            key = (label.aligned_window_id, label.group_id)
            window = windows_by_key.get(key)
            if window is None:
                raise DatasetInputError("Requested EMG target does not reference an accepted aligned window.")
            if label.source_feature_vector_id != window.source_feature_vector_id:
                raise DatasetInputError("Requested EMG target source does not match its aligned window.")
            target_values = values.setdefault(key, {})
            if label.metric_name in target_values:
                raise DatasetInputError("A requested EMG target appears more than once for one window.")
            target_values[label.metric_name] = label.value
        result: dict[tuple[str, str], tuple[NumericValue, ...]] = {}
        for key, target_values in values.items():
            if set(target_values) != requested:
                continue
            result[key] = tuple(
                NumericValue(name=f"target__{name}", value=target_values[name])
                for name in spec.target_metric_names
            )
        return result

    @staticmethod
    def _features_for(window: AlignedTrainingWindow, spec: DatasetBuildSpec) -> tuple[NumericValue, ...]:
        """Flatten only selected Smart Pod domains; EMG remains target-only."""

        values: list[NumericValue] = []
        for domain_name in spec.included_feature_domains:
            domain = window.smart_pod_features.get(domain_name)
            if domain is None:
                continue
            values.extend(
                NumericValue(name=f"feature__{domain_name}__{metric}", value=value)
                for metric, value in sorted(domain.biomarkers.items())
            )
        if not values:
            raise DatasetInputError("Accepted aligned window contains no selected Smart Pod features.")
        return tuple(values)

    @staticmethod
    def _dataset_id(spec: DatasetBuildSpec, sources: list[DatasetSource]) -> str:
        """Derive a stable ID from the exact policy and verified source evidence."""

        payload = {
            "spec": spec.model_dump(mode="json"),
            "sources": [source.model_dump(mode="json") for source in sources],
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"dataset-{digest[:24]}"
