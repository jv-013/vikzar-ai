"""Deterministic orchestration of model adapters, evaluation, and local evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.config import evaluation_config, experiment_config
from app.dataset_builder.builder import DatasetBuildResult
from app.dataset_builder.contracts import (
    DatasetSplit,
    TrainingExample,
    VersionedTrainingDataset,
)
from app.evaluation.contracts import (
    EvaluationReport,
    GroundTruthRow,
    PredictionProvenance,
    PredictionSet,
    ReleaseGatePolicy,
)
from app.evaluation.evaluator import EvaluationFramework

from .artifact_store import ExperimentArtifactStore
from .configuration import EnvironmentCollector, canonical_metadata
from .contracts import (
    ArtifactReference,
    ExecutionEnvironment,
    ExecutionSummary,
    ExperimentProvenance,
    ExperimentResult,
    ExperimentSpec,
    MetadataValue,
    ModelAdapterOutput,
    ModelCandidate,
    ModelCompatibility,
    ModelExecutionRequest,
    ModelInputRow,
    PromotionRecommendation,
)
from .exceptions import (
    ExperimentCompatibilityError,
    ExperimentError,
    ExperimentExecutionError,
)
from .locking import ExperimentLockManager
from .registry import ExperimentRegistry


class ModelAdapter(Protocol):
    """Permanent interface implemented by every future model family."""

    @property
    def algorithm_identifier(self) -> str:
        """Return the stable algorithm identity declared in an experiment spec."""

    def execute(self, request: ModelExecutionRequest) -> ModelAdapterOutput:
        """Train and predict behind the adapter boundary without framework model logic."""


class PredictionEvaluator(Protocol):
    """Phase 4 evaluation boundary consumed by the experiment runner."""

    def evaluate(
        self,
        prediction_set: PredictionSet,
        gate_policy: ReleaseGatePolicy | None = None,
    ) -> EvaluationReport:
        """Evaluate predictions using the permanent Phase 4 framework."""


class ExperimentRunner:
    """Coordinate one locked offline experiment without implementing an algorithm."""

    def __init__(
        self,
        artifact_store: ExperimentArtifactStore,
        *,
        evaluator: PredictionEvaluator | None = None,
        registry: ExperimentRegistry | None = None,
        lock_manager: ExperimentLockManager | None = None,
        environment_collector: EnvironmentCollector | None = None,
        clock: Callable[[], datetime] | None = None,
        application_version: str = experiment_config.ARCHITECTURE_VERSION,
        dependency_names: tuple[str, ...] = experiment_config.DEFAULT_DEPENDENCY_NAMES,
    ) -> None:
        self._store = artifact_store
        self._evaluator = evaluator or EvaluationFramework()
        self._registry = registry or ExperimentRegistry(artifact_store)
        self._locks = lock_manager or ExperimentLockManager(artifact_store.root)
        self._environment_collector = environment_collector or EnvironmentCollector()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._application_version = application_version
        self._dependency_names = dependency_names

    def run(
        self,
        *,
        spec: ExperimentSpec,
        dataset: DatasetBuildResult,
        adapter: ModelAdapter,
        gate_policy: ReleaseGatePolicy | None = None,
        recover: bool = False,
    ) -> ExperimentResult:
        """Execute one exclusive attempt and preserve all immutable evidence."""

        with self._locks.acquire(spec.experiment_id):
            duplicates = tuple(
                experiment_id
                for experiment_id in self._registry.experiments_for_configuration(
                    spec.configuration_hash
                )
                if experiment_id != spec.experiment_id
            )
            environment = self._environment_collector.collect(
                application_version=self._application_version,
                dependency_names=self._dependency_names,
            )
            run = self._registry.start(
                spec,
                environment,
                self._clock(),
                recover=recover,
            )
            try:
                request, evaluation_examples = self._prepare_request(
                    spec,
                    dataset,
                    adapter,
                )
                output = adapter.execute(request)
                prediction_set = self._prediction_set(
                    spec,
                    dataset,
                    output,
                    evaluation_examples,
                )
                report = self._evaluator.evaluate(prediction_set, gate_policy)
                self._validate_report(spec, output, report)
                result, result_reference = self._persist_result(
                    spec=spec,
                    run_id=run.run_id,
                    attempt=run.attempt,
                    started_at=run.started_at,
                    environment=environment,
                    output=output,
                    report=report,
                    duplicate_configuration_ids=duplicates,
                )
                completed = self._registry.completed(
                    run,
                    result.execution_summary.completed_at,
                    output.execution_metadata,
                    result.artifact_references + (result_reference,),
                )
                self._registry.record(completed)
                return result
            except (KeyboardInterrupt, SystemExit) as exc:
                metadata = canonical_metadata({"failure_type": type(exc).__name__})
                self._registry.record(
                    self._registry.interrupted(run, self._clock(), metadata)
                )
                raise
            except Exception as exc:
                metadata = canonical_metadata(
                    {
                        "failure_message": str(exc),
                        "failure_type": type(exc).__name__,
                    }
                )
                self._registry.record(self._registry.failed(run, self._clock(), metadata))
                if isinstance(exc, ExperimentError):
                    raise
                raise ExperimentExecutionError(
                    f"Experiment adapter execution failed: {spec.experiment_id}"
                ) from exc

    @staticmethod
    def _prepare_request(
        spec: ExperimentSpec,
        dataset: DatasetBuildResult,
        adapter: ModelAdapter,
    ) -> tuple[ModelExecutionRequest, tuple[TrainingExample, ...]]:
        ExperimentRunner._validate_spec(spec, dataset, adapter)
        training = tuple(
            example
            for example in dataset.examples
            if example.split is DatasetSplit.TRAIN
        )
        validation = tuple(
            example
            for example in dataset.examples
            if example.split is DatasetSplit.VALIDATION
            and spec.evaluation_split is not DatasetSplit.VALIDATION
        )
        evaluation = tuple(
            example
            for example in dataset.examples
            if example.split is spec.evaluation_split
        )
        if not training:
            raise ExperimentCompatibilityError(
                "Experiment dataset contains no training examples."
            )
        if not evaluation:
            raise ExperimentCompatibilityError(
                f"Experiment dataset contains no '{spec.evaluation_split.value}' examples."
            )
        inputs = tuple(
            ModelInputRow(
                example_id=example.example_id,
                player_id=example.player_id,
                session_id=example.session_id,
                features=example.features,
            )
            for example in evaluation
        )
        return (
            ModelExecutionRequest(
                spec=spec,
                dataset=dataset.dataset,
                training_examples=training,
                validation_examples=validation,
                prediction_inputs=inputs,
            ),
            evaluation,
        )

    @staticmethod
    def _validate_spec(
        spec: ExperimentSpec,
        dataset: DatasetBuildResult,
        adapter: ModelAdapter,
    ) -> None:
        manifest = dataset.dataset
        expected_checksum = ExperimentRunner.dataset_manifest_checksum(manifest)
        checks = {
            "dataset ID": spec.dataset_id == manifest.dataset_id,
            "dataset version": spec.dataset_version == manifest.schema_version,
            "dataset checksum": spec.dataset_checksum.lower() == expected_checksum,
            "feature schema version": spec.feature_schema_version == manifest.schema_version,
            "target schema version": spec.target_schema_version == manifest.schema_version,
            "evaluation framework version": (
                spec.evaluation_framework_version
                == evaluation_config.EVALUATION_SCHEMA_VERSION
            ),
            "algorithm identifier": spec.algorithm_identifier == adapter.algorithm_identifier,
        }
        failed = tuple(name for name, passed in checks.items() if not passed)
        if failed:
            raise ExperimentCompatibilityError(
                "Experiment specification is incompatible with: " + ", ".join(failed)
            )

    @staticmethod
    def _prediction_set(
        spec: ExperimentSpec,
        dataset: DatasetBuildResult,
        output: ModelAdapterOutput,
        evaluation_examples: tuple[TrainingExample, ...],
    ) -> PredictionSet:
        schema = dataset.dataset.feature_schema
        checks = {
            "feature schema": output.feature_schema == schema.feature_names,
            "target schema": output.target_schema == schema.target_names,
        }
        failed = tuple(name for name, passed in checks.items() if not passed)
        if failed:
            raise ExperimentCompatibilityError(
                "Model adapter output is incompatible with the dataset "
                + ", ".join(failed)
                + "."
            )
        truth_rows = tuple(
            GroundTruthRow(
                example_id=example.example_id,
                target_name=target.name,
                value=target.value,
                player_id=example.player_id,
                session_id=example.session_id,
                dataset_split=example.split,
            )
            for example in evaluation_examples
            for target in example.targets
        )
        try:
            return PredictionSet(
                model_id=output.model_id,
                model_version=output.model_version,
                dataset_id=dataset.dataset.dataset_id,
                split_id=spec.evaluation_split,
                prediction_rows=output.prediction_rows,
                ground_truth_rows=truth_rows,
                provenance=PredictionProvenance(
                    dataset_schema_version=dataset.dataset.schema_version,
                    dataset_manifest_sha256=spec.dataset_checksum,
                    dataset_created_at=dataset.dataset.created_at,
                    feature_schema_names=schema.feature_names,
                    target_names=schema.target_names,
                ),
            )
        except ValueError as exc:
            raise ExperimentCompatibilityError(
                "Model predictions are incompatible with held-out dataset evidence."
            ) from exc

    @staticmethod
    def _validate_report(
        spec: ExperimentSpec,
        output: ModelAdapterOutput,
        report: EvaluationReport,
    ) -> None:
        provenance = report.provenance
        checks = {
            "evaluation schema version": report.schema_version
            == spec.evaluation_framework_version,
            "model ID": provenance.model_id == output.model_id,
            "model version": provenance.model_version == output.model_version,
            "dataset ID": provenance.dataset_id == spec.dataset_id,
            "dataset checksum": provenance.dataset_manifest_sha256.lower()
            == spec.dataset_checksum.lower(),
            "evaluation split": provenance.split_id is spec.evaluation_split,
            "embedded report checksum": report.report_checksum
            == ExperimentRunner.evaluation_report_checksum(report),
        }
        failed = tuple(name for name, passed in checks.items() if not passed)
        if failed:
            raise ExperimentCompatibilityError(
                "Evaluation report is incompatible with: " + ", ".join(failed)
            )

    def _persist_result(
        self,
        *,
        spec: ExperimentSpec,
        run_id: str,
        attempt: int,
        started_at: datetime,
        environment: ExecutionEnvironment,
        output: ModelAdapterOutput,
        report: EvaluationReport,
        duplicate_configuration_ids: tuple[str, ...],
    ) -> tuple[ExperimentResult, ArtifactReference]:
        base = f"experiments/{spec.experiment_id}/attempt-{attempt:04d}"
        model_reference = self._store.write_bytes(
            relative_path=f"{base}/model.bin",
            artifact_type="model_candidate",
            payload=output.model_artifact,
            media_type=output.model_artifact_media_type,
        )
        report_reference = self._store.write_json(
            relative_path=f"{base}/evaluation_report.json",
            artifact_type="evaluation_report",
            payload=report,
        )
        candidate = ModelCandidate(
            model_id=output.model_id,
            model_version=output.model_version,
            feature_schema=output.feature_schema,
            target_schema=output.target_schema,
            artifact_reference=model_reference,
            compatibility=ModelCompatibility(
                compatible=True,
                reasons=("Dataset and evaluation lineage are compatible.",),
            ),
        )
        recommendation = PromotionRecommendation(
            eligible=report.release_approved,
            reasons=(
                ("All external Phase 4 release gates passed.",)
                if report.release_approved
                else report.failed_checks
            ),
        )
        warnings = (
            (
                "Identical configuration already registered for experiment IDs: "
                + ", ".join(duplicate_configuration_ids),
            )
            if duplicate_configuration_ids
            else ()
        )
        provenance = ExperimentProvenance(
            framework_schema_version=experiment_config.EXPERIMENT_FRAMEWORK_SCHEMA_VERSION,
            configuration_hash=spec.configuration_hash,
            dataset_id=spec.dataset_id,
            dataset_version=spec.dataset_version,
            dataset_checksum=spec.dataset_checksum,
            evaluation_report_id=report.report_id,
            evaluation_report_checksum=report.report_checksum,
            model_artifact_checksum=model_reference.sha256,
        )
        reproducibility_checksum = self._reproducibility_checksum(
            spec=spec,
            candidate=candidate,
            report=report,
            provenance=provenance,
        )
        result = ExperimentResult(
            result_id=f"{spec.experiment_id}:result",
            spec=spec,
            model_candidate=candidate,
            evaluation_report=report,
            execution_summary=ExecutionSummary(
                run_id=run_id,
                attempt=attempt,
                started_at=started_at,
                completed_at=self._clock(),
                environment=environment,
                execution_metadata=output.execution_metadata,
            ),
            promotion_recommendation=recommendation,
            warnings=warnings,
            artifact_references=(model_reference, report_reference),
            provenance=provenance,
            reproducibility_checksum=reproducibility_checksum,
        )
        result_reference = self._store.write_json(
            relative_path=f"{base}/result.json",
            artifact_type="experiment_result",
            payload=result,
        )
        return result, result_reference

    @staticmethod
    def _reproducibility_checksum(
        *,
        spec: ExperimentSpec,
        candidate: ModelCandidate,
        report: EvaluationReport,
        provenance: ExperimentProvenance,
    ) -> str:
        payload = {
            "configuration_hash": spec.configuration_hash,
            "dataset_checksum": spec.dataset_checksum.lower(),
            "evaluation_report_checksum": report.report_checksum.lower(),
            "model_artifact_checksum": provenance.model_artifact_checksum.lower(),
            "model_id": candidate.model_id,
            "model_version": candidate.model_version,
            "feature_schema": candidate.feature_schema,
            "target_schema": candidate.target_schema,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def dataset_manifest_checksum(manifest: VersionedTrainingDataset) -> str:
        """Return the exact checksum used by Phase 3 ``dataset.json`` storage."""

        encoded = (
            json.dumps(
                manifest.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def evaluation_report_checksum(report: EvaluationReport) -> str:
        """Recalculate the embedded checksum defined by Phase 4."""

        payload = report.model_dump(
            mode="json",
            exclude={"report_id", "report_checksum"},
        )
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
