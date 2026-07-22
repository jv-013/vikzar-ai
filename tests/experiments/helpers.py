"""Normal Phase 3 evidence and deterministic adapters for experiment tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Event

from app.config import evaluation_config
from app.dataset_builder import (
    DatasetBuildSpec,
    DatasetBuilder,
    DatasetSplit,
    DatasetSplitPolicy,
)
from app.dataset_builder.builder import DatasetBuildResult
from app.evaluation.contracts import PredictionRow
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import (
    ExperimentCreationMetadata,
    ExperimentSpec,
    ModelAdapterOutput,
    ModelExecutionRequest,
)
from app.experiments.runner import ExperimentRunner
from tests.dataset_builder.helpers import make_verified_session


def make_experiment_dataset() -> DatasetBuildResult:
    """Build synthetic evidence through the unmodified Phase 3 pipeline."""

    sessions = []
    for index in range(8):
        session = make_verified_session(
            capture_session_id=f"experiment-capture-{index}",
            player_id=f"experiment-player-{index}",
            session_id=f"experiment-session-{index}",
        )
        labels = tuple(
            label.model_copy(
                update={
                    "value": (
                        0.1 * (index + 1)
                        if label.metric_name == "quadriceps_rms"
                        else 0.05 * (index + 1)
                    )
                }
            )
            for label in session.labels
        )
        sessions.append(session.model_copy(update={"labels": labels}))
    return DatasetBuilder().build(
        sessions,
        DatasetBuildSpec(
            dataset_name="phase-five-normal-synthetic-dataset",
            target_metric_names=("quadriceps_rms", "hamstring_rms"),
            split_policy=DatasetSplitPolicy(
                train_fraction=0.5,
                validation_fraction=0.25,
                test_fraction=0.25,
                seed="phase-five-split",
            ),
        ),
    )


def make_spec(
    dataset: DatasetBuildResult,
    *,
    experiment_id: str = "exp_20260719_001",
    algorithm_identifier: str = "deterministic-mock",
    seed: int = 41,
) -> ExperimentSpec:
    """Create a valid immutable spec from exact Phase 3 lineage."""

    return ExperimentSpec.create(
        experiment_id=experiment_id,
        dataset_id=dataset.dataset.dataset_id,
        dataset_version=dataset.dataset.schema_version,
        dataset_checksum=ExperimentRunner.dataset_manifest_checksum(dataset.dataset),
        feature_schema_version=dataset.dataset.schema_version,
        target_schema_version=dataset.dataset.schema_version,
        evaluation_framework_version=evaluation_config.EVALUATION_SCHEMA_VERSION,
        evaluation_split=DatasetSplit.TEST,
        algorithm_identifier=algorithm_identifier,
        hyperparameters=canonical_metadata({"alpha": 0.5, "fit_intercept": True}),
        random_seed=seed,
        notes="Permanent deterministic test experiment.",
        creation_metadata=ExperimentCreationMetadata(
            created_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            created_by="phase-five-tests",
        ),
    )


class DeterministicMockAdapter:
    """Deterministic adapter with truth supplied only by its test constructor."""

    algorithm_identifier = "deterministic-mock"

    def __init__(
        self,
        dataset: DatasetBuildResult,
        *,
        offset: float = 0.0,
        started: Event | None = None,
        release: Event | None = None,
    ) -> None:
        self._targets = {
            (example.example_id, target.name): target.value
            for example in dataset.examples
            for target in example.targets
        }
        self._offset = offset
        self._started = started
        self._release = release
        self.observed_request: ModelExecutionRequest | None = None

    def execute(self, request: ModelExecutionRequest) -> ModelAdapterOutput:
        """Return stable artifact bytes and predictions in canonical order."""

        self.observed_request = request
        if self._started is not None:
            self._started.set()
        if self._release is not None:
            self._release.wait(timeout=10)
        prediction_keys = sorted(
            (input_row.example_id, target_name)
            for input_row in request.prediction_inputs
            for target_name in request.dataset.feature_schema.target_names
        )
        predictions = tuple(
            PredictionRow(
                example_id=example_id,
                target_name=target_name,
                value=self._targets[(example_id, target_name)] + self._offset,
                confidence=0.95,
            )
            for example_id, target_name in prediction_keys
        )
        artifact = json.dumps(
            {
                "algorithm": self.algorithm_identifier,
                "configuration_hash": request.spec.configuration_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ModelAdapterOutput(
            model_id="deterministic-mock-model",
            model_version="1.0.0",
            feature_schema=request.dataset.feature_schema.feature_names,
            target_schema=request.dataset.feature_schema.target_names,
            model_artifact=artifact,
            model_artifact_media_type="application/json",
            prediction_rows=predictions,
            execution_metadata=canonical_metadata({"epochs": 0, "trainer": "mock"}),
        )


class InterruptingAdapter:
    """Adapter used to exercise durable interruption recovery."""

    algorithm_identifier = "deterministic-mock"

    def execute(self, request: ModelExecutionRequest) -> ModelAdapterOutput:
        """Interrupt after the registry has recorded a running attempt."""

        del request
        raise KeyboardInterrupt
