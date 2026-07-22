"""Deterministic Phase 3 evidence and Phase 5 requests for benchmark tests."""

from __future__ import annotations

from datetime import datetime, timezone

from app.config import evaluation_config
from app.dataset_builder import (
    DatasetBuildSpec,
    DatasetBuilder,
    DatasetSplit,
    DatasetSplitPolicy,
)
from app.dataset_builder.builder import DatasetBuildResult
from app.experiments.contracts import (
    ExperimentCreationMetadata,
    ExperimentSpec,
    ModelExecutionRequest,
    ModelInputRow,
)
from app.experiments.runner import ExperimentRunner
from app.models.benchmark_base import BenchmarkRegressionAdapter
from tests.dataset_builder.helpers import make_verified_session


def make_benchmark_dataset() -> DatasetBuildResult:
    """Build fixed nonlinear-feature, linear-target evidence through Phase 3."""

    generated_at = datetime(2026, 7, 19, 10, tzinfo=timezone.utc)
    sessions = []
    for index in range(1, 16):
        x_value = float(index)
        quadratic = x_value * x_value
        session = make_verified_session(
            capture_session_id=f"benchmark-capture-{index:02d}",
            player_id=f"benchmark-player-{index:02d}",
            session_id=f"benchmark-session-{index:02d}",
        )
        window = session.aligned_windows[0]
        motion = window.smart_pod_features["motion"].model_copy(
            update={
                "biomarkers": {
                    "mean_angular_velocity": quadratic,
                    "peak_resultant_acceleration": x_value,
                }
            }
        )
        updated_window = window.model_copy(
            update={"smart_pod_features": {"motion": motion}}
        )
        labels = tuple(
            label.model_copy(
                update={
                    "value": (
                        1.0 + 2.0 * x_value + 0.5 * quadratic
                        if label.metric_name == "quadriceps_rms"
                        else -2.0 + 0.25 * x_value - 0.1 * quadratic
                    )
                }
            )
            for label in session.labels
        )
        sessions.append(
            session.model_copy(
                update={
                    "aligned_windows": (updated_window,),
                    "labels": labels,
                    "provenance": session.provenance.model_copy(
                        update={"generated_at": generated_at}
                    ),
                }
            )
        )
    return DatasetBuilder().build(
        sessions,
        DatasetBuildSpec(
            dataset_name="phase-six-permanent-benchmarks",
            target_metric_names=("quadriceps_rms", "hamstring_rms"),
            split_policy=DatasetSplitPolicy(
                train_fraction=0.6,
                validation_fraction=0.2,
                test_fraction=0.2,
                seed="phase-six-fixed-split",
            ),
        ),
    )


def make_execution_request(
    dataset: DatasetBuildResult,
    adapter: BenchmarkRegressionAdapter,
    *,
    experiment_id: str = "benchmark-unit-001",
) -> ModelExecutionRequest:
    """Create the exact immutable Phase 5 request used by benchmark adapters."""

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
        algorithm_identifier=adapter.algorithm_identifier,
        hyperparameters=adapter.hyperparameters,
        random_seed=adapter.random_seed,
        creation_metadata=ExperimentCreationMetadata(
            created_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            created_by="phase-six-tests",
        ),
    )
    training = tuple(
        example for example in dataset.examples if example.split is DatasetSplit.TRAIN
    )
    validation = tuple(
        example
        for example in dataset.examples
        if example.split is DatasetSplit.VALIDATION
    )
    prediction_examples = tuple(
        example for example in dataset.examples if example.split is DatasetSplit.TEST
    )
    return ModelExecutionRequest(
        spec=spec,
        dataset=manifest,
        training_examples=training,
        validation_examples=validation,
        prediction_inputs=tuple(
            ModelInputRow(
                example_id=example.example_id,
                player_id=example.player_id,
                session_id=example.session_id,
                features=example.features,
            )
            for example in prediction_examples
        ),
    )
