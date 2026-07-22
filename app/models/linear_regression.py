"""Permanent ordinary least-squares multi-output regression benchmark."""

from __future__ import annotations

import numpy as np

from app.config import benchmark_config
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import MetadataValue, ModelExecutionRequest

from .benchmark_base import BenchmarkRegressionAdapter
from .benchmark_contracts import BenchmarkModelArtifact


class LinearRegressionAdapter(BenchmarkRegressionAdapter):
    """Fit deterministic ordinary least squares with an optional intercept."""

    def __init__(
        self,
        *,
        fit_intercept: bool = True,
        random_seed: int = benchmark_config.DEFAULT_RANDOM_SEED,
    ) -> None:
        super().__init__(random_seed=random_seed)
        self._fit_intercept = fit_intercept

    @property
    def algorithm_identifier(self) -> str:
        """Return the permanent ordinary least-squares identity."""

        return benchmark_config.LINEAR_REGRESSION_ALGORITHM

    @property
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return the immutable least-squares configuration."""

        return canonical_metadata(
            {
                "fit_intercept": self._fit_intercept,
                "solver": "numpy_lstsq",
            }
        )

    def _fit_artifact(
        self,
        *,
        request: ModelExecutionRequest,
        model_id: str,
        features: np.ndarray,
        targets: np.ndarray,
    ) -> BenchmarkModelArtifact:
        design = (
            np.column_stack((np.ones(features.shape[0], dtype=np.float64), features))
            if self._fit_intercept
            else features
        )
        solution, _, _, _ = np.linalg.lstsq(design, targets, rcond=None)
        if self._fit_intercept:
            intercepts = solution[0]
            coefficients = solution[1:].T
        else:
            intercepts = np.zeros(targets.shape[1], dtype=np.float64)
            coefficients = solution.T
        return self._artifact(
            request=request,
            model_id=model_id,
            coefficients=tuple(
                tuple(float(value) for value in row) for row in coefficients
            ),
            intercepts=tuple(float(value) for value in intercepts),
        )
