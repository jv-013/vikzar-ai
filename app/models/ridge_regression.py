"""Permanent L2-regularized multi-output linear regression benchmark."""

from __future__ import annotations

import math

import numpy as np

from app.config import benchmark_config
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import MetadataValue, ModelExecutionRequest

from .benchmark_base import BenchmarkRegressionAdapter
from .benchmark_contracts import BenchmarkModelArtifact
from .exceptions import BenchmarkConfigurationError


class RidgeRegressionAdapter(BenchmarkRegressionAdapter):
    """Fit deterministic closed-form L2-regularized regression."""

    def __init__(
        self,
        *,
        alpha: float = benchmark_config.DEFAULT_RIDGE_ALPHA,
        fit_intercept: bool = True,
        random_seed: int = benchmark_config.DEFAULT_RANDOM_SEED,
    ) -> None:
        if not math.isfinite(alpha) or alpha <= 0:
            raise BenchmarkConfigurationError("Ridge alpha must be finite and positive.")
        super().__init__(random_seed=random_seed)
        self._alpha = alpha
        self._fit_intercept = fit_intercept

    @property
    def algorithm_identifier(self) -> str:
        """Return the permanent ridge-regression identity."""

        return benchmark_config.RIDGE_REGRESSION_ALGORITHM

    @property
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return the immutable ridge configuration."""

        return canonical_metadata(
            {
                "alpha": self._alpha,
                "fit_intercept": self._fit_intercept,
                "solver": "closed_form",
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
        if self._fit_intercept:
            feature_mean = features.mean(axis=0)
            target_mean = targets.mean(axis=0)
            centered_features = features - feature_mean
            centered_targets = targets - target_mean
        else:
            feature_mean = np.zeros(features.shape[1], dtype=np.float64)
            target_mean = np.zeros(targets.shape[1], dtype=np.float64)
            centered_features = features
            centered_targets = targets
        gram = centered_features.T @ centered_features
        regularized = gram + self._alpha * np.eye(features.shape[1], dtype=np.float64)
        coefficients_by_feature = np.linalg.solve(
            regularized,
            centered_features.T @ centered_targets,
        )
        intercepts = target_mean - feature_mean @ coefficients_by_feature
        coefficients = coefficients_by_feature.T
        return self._artifact(
            request=request,
            model_id=model_id,
            coefficients=tuple(
                tuple(float(value) for value in row) for row in coefficients
            ),
            intercepts=tuple(float(value) for value in intercepts),
        )
