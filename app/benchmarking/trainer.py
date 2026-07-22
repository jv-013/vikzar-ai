"""Automatic Phase 5 experiment creation for permanent benchmark adapters."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.config import evaluation_config
from app.dataset_builder.builder import DatasetBuildResult
from app.dataset_builder.contracts import DatasetSplit
from app.evaluation.contracts import ReleaseGatePolicy
from app.experiments.contracts import (
    ExperimentCreationMetadata,
    ExperimentResult,
    ExperimentSpec,
    MetadataValue,
)
from app.experiments.runner import ExperimentRunner, ModelAdapter


class BenchmarkAdapter(ModelAdapter, Protocol):
    """Phase 6 adapter metadata required for automatic experiment creation."""

    @property
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return canonical benchmark hyperparameters."""

    @property
    def random_seed(self) -> int:
        """Return the deterministic training seed."""


class BenchmarkTrainer:
    """Create, register, train, evaluate, and persist one benchmark experiment."""

    def __init__(
        self,
        experiment_runner: ExperimentRunner,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._experiment_runner = experiment_runner
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def run(
        self,
        *,
        experiment_id: str,
        dataset: DatasetBuildResult,
        adapter: BenchmarkAdapter,
        created_by: str,
        evaluation_split: DatasetSplit = DatasetSplit.TEST,
        gate_policy: ReleaseGatePolicy | None = None,
        notes: str | None = None,
    ) -> ExperimentResult:
        """Create an immutable spec and execute it through Phases 5 and 4."""

        manifest = dataset.dataset
        spec = ExperimentSpec.create(
            experiment_id=experiment_id,
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.schema_version,
            dataset_checksum=ExperimentRunner.dataset_manifest_checksum(manifest),
            feature_schema_version=manifest.schema_version,
            target_schema_version=manifest.schema_version,
            evaluation_framework_version=evaluation_config.EVALUATION_SCHEMA_VERSION,
            evaluation_split=evaluation_split,
            algorithm_identifier=adapter.algorithm_identifier,
            hyperparameters=adapter.hyperparameters,
            random_seed=adapter.random_seed,
            notes=notes,
            creation_metadata=ExperimentCreationMetadata(
                created_at=self._clock(),
                created_by=created_by,
                source="offline_benchmark",
            ),
        )
        return self._experiment_runner.run(
            spec=spec,
            dataset=dataset,
            adapter=adapter,
            gate_policy=gate_policy,
        )
