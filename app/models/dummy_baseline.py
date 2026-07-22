"""Permanent mean-prediction reference benchmark for continuous EMG targets."""

from __future__ import annotations

import numpy as np

from app.config import benchmark_config
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import MetadataValue, ModelExecutionRequest

from .benchmark_base import BenchmarkRegressionAdapter
from .benchmark_contracts import BenchmarkModelArtifact


class DummyMeanRegressorAdapter(BenchmarkRegressionAdapter):
    """Predict each target's training mean as the minimum scientific reference."""

    def __init__(self, *, random_seed: int = benchmark_config.DEFAULT_RANDOM_SEED) -> None:
        super().__init__(random_seed=random_seed)

    @property
    def algorithm_identifier(self) -> str:
        """Return the permanent dummy-regression identity."""

        return benchmark_config.DUMMY_MEAN_ALGORITHM

    @property
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return the immutable mean-strategy declaration."""

        return canonical_metadata({"strategy": "mean"})

    def _fit_artifact(
        self,
        *,
        request: ModelExecutionRequest,
        model_id: str,
        features: np.ndarray,
        targets: np.ndarray,
    ) -> BenchmarkModelArtifact:
        del features
        return self._artifact(
            request=request,
            model_id=model_id,
            constant_values=tuple(float(value) for value in targets.mean(axis=0)),
        )
