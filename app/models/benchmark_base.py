"""Shared deterministic Phase 5 adapter implementation for regression benchmarks."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np

from app.config import benchmark_config
from app.dataset_builder.contracts import NumericValue, TrainingExample
from app.evaluation.contracts import PredictionRow
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import (
    MetadataValue,
    ModelAdapterOutput,
    ModelExecutionRequest,
    ModelInputRow,
)

from .benchmark_contracts import BenchmarkModelArtifact
from .exceptions import BenchmarkConfigurationError, BenchmarkDataError
from .serialization import BenchmarkModelSerializer


class BenchmarkRegressionAdapter(ABC):
    """Base adapter that enforces schemas, provenance, and artifact-backed prediction."""

    model_version = benchmark_config.BENCHMARK_MODEL_SCHEMA_VERSION

    def __init__(self, *, random_seed: int) -> None:
        self._random_seed = random_seed

    @property
    @abstractmethod
    def algorithm_identifier(self) -> str:
        """Return the permanent algorithm identifier."""

    @property
    @abstractmethod
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return canonical hyperparameters included in the configuration hash."""

    @property
    def random_seed(self) -> int:
        """Return the deterministic seed recorded by Phase 5."""

        return self._random_seed

    def execute(self, request: ModelExecutionRequest) -> ModelAdapterOutput:
        """Fit, serialize, reload, and predict through the Phase 5 adapter contract."""

        self._validate_spec(request)
        feature_schema = request.dataset.feature_schema.feature_names
        target_schema = request.dataset.feature_schema.target_names
        training_features = self._training_feature_matrix(
            request.training_examples,
            feature_schema,
        )
        training_targets = self._training_target_matrix(
            request.training_examples,
            target_schema,
        )
        model_id = (
            f"{self.algorithm_identifier}-"
            f"{request.spec.configuration_hash[:24]}"
        )
        artifact = self._fit_artifact(
            request=request,
            model_id=model_id,
            features=training_features,
            targets=training_targets,
        )
        serialized = BenchmarkModelSerializer.dumps(artifact)
        loaded = BenchmarkModelSerializer.loads(
            serialized,
            expected_sha256=hashlib.sha256(serialized).hexdigest(),
        )
        prediction_features = self._prediction_feature_matrix(
            request.prediction_inputs,
            feature_schema,
        )
        predicted = loaded.predict(prediction_features)
        prediction_rows = tuple(
            sorted(
                (
                    PredictionRow(
                        example_id=input_row.example_id,
                        target_name=target_name,
                        value=float(predicted[row_index, target_index]),
                    )
                    for row_index, input_row in enumerate(request.prediction_inputs)
                    for target_index, target_name in enumerate(target_schema)
                ),
                key=lambda row: (row.example_id, row.target_name),
            )
        )
        return ModelAdapterOutput(
            model_id=model_id,
            model_version=self.model_version,
            feature_schema=feature_schema,
            target_schema=target_schema,
            model_artifact=serialized,
            model_artifact_media_type=benchmark_config.BENCHMARK_MODEL_MEDIA_TYPE,
            prediction_rows=prediction_rows,
            execution_metadata=canonical_metadata(
                {
                    "evaluation_example_count": len(request.prediction_inputs),
                    "feature_count": len(feature_schema),
                    "target_count": len(target_schema),
                    "training_example_count": len(request.training_examples),
                    "validation_example_count": len(request.validation_examples),
                }
            ),
        )

    @abstractmethod
    def _fit_artifact(
        self,
        *,
        request: ModelExecutionRequest,
        model_id: str,
        features: np.ndarray,
        targets: np.ndarray,
    ) -> BenchmarkModelArtifact:
        """Fit algorithm state and return its immutable artifact contract."""

    def _artifact(
        self,
        *,
        request: ModelExecutionRequest,
        model_id: str,
        **payload: object,
    ) -> BenchmarkModelArtifact:
        return BenchmarkModelArtifact(
            algorithm_identifier=self.algorithm_identifier,
            model_id=model_id,
            model_version=self.model_version,
            configuration_hash=request.spec.configuration_hash,
            random_seed=self.random_seed,
            feature_schema=request.dataset.feature_schema.feature_names,
            target_schema=request.dataset.feature_schema.target_names,
            hyperparameters=self.hyperparameters,
            **payload,
        )

    def _validate_spec(self, request: ModelExecutionRequest) -> None:
        checks = {
            "algorithm identifier": request.spec.algorithm_identifier
            == self.algorithm_identifier,
            "hyperparameters": request.spec.hyperparameters == self.hyperparameters,
            "random seed": request.spec.random_seed == self.random_seed,
        }
        failed = tuple(name for name, passed in checks.items() if not passed)
        if failed:
            raise BenchmarkConfigurationError(
                "Benchmark adapter disagrees with experiment " + ", ".join(failed) + "."
            )

    @staticmethod
    def _training_feature_matrix(
        examples: tuple[TrainingExample, ...],
        schema: tuple[str, ...],
    ) -> np.ndarray:
        return BenchmarkRegressionAdapter._named_matrix(
            tuple(example.features for example in examples),
            schema,
            "training feature",
        )

    @staticmethod
    def _training_target_matrix(
        examples: tuple[TrainingExample, ...],
        schema: tuple[str, ...],
    ) -> np.ndarray:
        return BenchmarkRegressionAdapter._named_matrix(
            tuple(example.targets for example in examples),
            schema,
            "training target",
        )

    @staticmethod
    def _prediction_feature_matrix(
        rows: tuple[ModelInputRow, ...],
        schema: tuple[str, ...],
    ) -> np.ndarray:
        return BenchmarkRegressionAdapter._named_matrix(
            tuple(row.features for row in rows),
            schema,
            "prediction feature",
        )

    @staticmethod
    def _named_matrix(
        rows: tuple[tuple[NumericValue, ...], ...],
        schema: tuple[str, ...],
        description: str,
    ) -> np.ndarray:
        if not rows:
            raise BenchmarkDataError(f"At least one {description} row is required.")
        if any(tuple(value.name for value in row) != schema for row in rows):
            raise BenchmarkDataError(f"{description.title()} ordering does not match its schema.")
        matrix = np.asarray(
            [[value.value for value in row] for row in rows],
            dtype=np.float64,
        )
        if matrix.ndim != 2 or not np.isfinite(matrix).all():
            raise BenchmarkDataError(f"{description.title()} values must form a finite matrix.")
        return matrix
