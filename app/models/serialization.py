"""Canonical deterministic serialization and loading for benchmark models."""

from __future__ import annotations

import hashlib
import json

import numpy as np
from pydantic import ValidationError

from app.config import benchmark_config

from .benchmark_contracts import BenchmarkModelArtifact, BenchmarkTreeNode
from .exceptions import BenchmarkDataError, BenchmarkSerializationError


class LoadedBenchmarkModel:
    """Immutable loaded predictive model backed only by validated artifact state."""

    def __init__(self, artifact: BenchmarkModelArtifact) -> None:
        self._artifact = artifact

    @property
    def artifact(self) -> BenchmarkModelArtifact:
        """Return the validated immutable artifact contract."""

        return self._artifact

    def predict(self, features: np.ndarray) -> np.ndarray:
        """Predict a finite two-dimensional feature matrix deterministically."""

        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != len(self._artifact.feature_schema):
            raise BenchmarkDataError("Prediction matrix does not match the model feature schema.")
        if not np.isfinite(matrix).all():
            raise BenchmarkDataError("Prediction features must be finite.")
        algorithm = self._artifact.algorithm_identifier
        if algorithm == benchmark_config.DUMMY_MEAN_ALGORITHM:
            constants = np.asarray(self._artifact.constant_values, dtype=np.float64)
            return np.tile(constants, (matrix.shape[0], 1))
        if algorithm in {
            benchmark_config.LINEAR_REGRESSION_ALGORITHM,
            benchmark_config.RIDGE_REGRESSION_ALGORITHM,
        }:
            coefficients = np.asarray(self._artifact.coefficients, dtype=np.float64)
            intercepts = np.asarray(self._artifact.intercepts, dtype=np.float64)
            return matrix @ coefficients.T + intercepts
        if algorithm == benchmark_config.RANDOM_FOREST_ALGORITHM:
            predictions = np.zeros(
                (matrix.shape[0], len(self._artifact.target_schema)),
                dtype=np.float64,
            )
            for tree in self._artifact.trees:
                predictions += np.asarray(
                    [self._predict_tree(tree.root, row) for row in matrix],
                    dtype=np.float64,
                )
            return predictions / len(self._artifact.trees)
        raise BenchmarkSerializationError("Loaded artifact uses an unsupported algorithm.")

    @staticmethod
    def _predict_tree(node: BenchmarkTreeNode, row: np.ndarray) -> tuple[float, ...]:
        current = node
        while current.feature_index is not None:
            if current.left is None or current.right is None or current.threshold is None:
                raise BenchmarkSerializationError("Loaded tree contains an incomplete split.")
            current = (
                current.left
                if row[current.feature_index] <= current.threshold
                else current.right
            )
        return current.prediction


class BenchmarkModelSerializer:
    """Serialize validated models as canonical UTF-8 JSON rather than unsafe pickle."""

    @staticmethod
    def dumps(artifact: BenchmarkModelArtifact) -> bytes:
        """Return byte-for-byte deterministic model artifact content."""

        return (
            json.dumps(
                artifact.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def loads(
        payload: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> LoadedBenchmarkModel:
        """Verify and load canonical benchmark artifact bytes."""

        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and actual_sha256 != expected_sha256.lower():
            raise BenchmarkSerializationError("Benchmark model checksum verification failed.")
        try:
            artifact = BenchmarkModelArtifact.model_validate_json(payload)
        except (ValidationError, ValueError, UnicodeDecodeError) as exc:
            raise BenchmarkSerializationError("Benchmark model artifact is invalid.") from exc
        if BenchmarkModelSerializer.dumps(artifact) != payload:
            raise BenchmarkSerializationError("Benchmark model artifact is not canonical JSON.")
        return LoadedBenchmarkModel(artifact)
