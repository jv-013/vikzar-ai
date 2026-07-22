"""Final offline production training pipeline over Phases 3–6."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from app.config import evaluation_config, production_model_config
from app.dataset_builder.builder import DatasetBuildResult
from app.dataset_builder.contracts import DatasetSplit
from app.evaluation.contracts import ReleaseGatePolicy
from app.experiments.contracts import (
    ExperimentCreationMetadata,
    ExperimentResult,
    ExperimentSpec,
)
from app.experiments.runner import ExperimentRunner

from .configuration import ProductionModelConfig
from .contracts import ProductionTrainingOutcome
from .factory import ProductionModelFactory
from .registry import ProductionModelRegistry
from .selection import ProductionModelSelector


class ProductionTrainer:
    """Train, evaluate, register, and benchmark one production candidate."""

    def __init__(
        self,
        experiment_runner: ExperimentRunner,
        registry: ProductionModelRegistry,
        *,
        selector: ProductionModelSelector | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._experiment_runner = experiment_runner
        self._registry = registry
        self._selector = selector or ProductionModelSelector()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def run(
        self,
        *,
        experiment_id: str,
        dataset: DatasetBuildResult,
        config: ProductionModelConfig,
        benchmark_results: tuple[ExperimentResult, ...],
        created_by: str,
        gate_policy: ReleaseGatePolicy | None = None,
        notes: str | None = None,
    ) -> ProductionTrainingOutcome:
        """Execute the complete offline production lifecycle and comparison."""

        adapter = ProductionModelFactory.create(config)
        manifest = dataset.dataset
        spec = ExperimentSpec.create(
            experiment_id=experiment_id,
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.schema_version,
            dataset_checksum=ExperimentRunner.dataset_manifest_checksum(manifest),
            feature_schema_version=manifest.schema_version,
            target_schema_version=manifest.schema_version,
            evaluation_framework_version=evaluation_config.EVALUATION_SCHEMA_VERSION,
            evaluation_split=DatasetSplit.TEST,
            algorithm_identifier=production_model_config.PRODUCTION_MODEL_ALGORITHM,
            hyperparameters=adapter.hyperparameters,
            random_seed=adapter.random_seed,
            notes=notes,
            creation_metadata=ExperimentCreationMetadata(
                created_at=self._clock(),
                created_by=created_by,
                source="offline_production_training",
            ),
        )
        result = self._experiment_runner.run(
            spec=spec,
            dataset=dataset,
            adapter=adapter,
            gate_policy=gate_policy,
        )
        registration, registration_reference = self._registry.register(result)
        selection = self._selector.select(result, benchmark_results)
        selection_reference = self._registry.register_selection(selection)
        return ProductionTrainingOutcome(
            experiment_result=result,
            registration=registration,
            selection=selection,
            registration_artifact=registration_reference,
            selection_artifact=selection_reference,
        )
