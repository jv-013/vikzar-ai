"""Permanent deterministic multi-output random-forest regression benchmark."""

from __future__ import annotations

import math

import numpy as np

from app.config import benchmark_config
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import MetadataValue, ModelExecutionRequest

from .benchmark_base import BenchmarkRegressionAdapter
from .benchmark_contracts import (
    BenchmarkModelArtifact,
    BenchmarkTree,
    BenchmarkTreeNode,
)
from .exceptions import BenchmarkConfigurationError


class RandomForestRegressorAdapter(BenchmarkRegressionAdapter):
    """Fit deterministic bootstrap CART trees using squared-error splits."""

    def __init__(
        self,
        *,
        n_estimators: int = benchmark_config.DEFAULT_RANDOM_FOREST_ESTIMATORS,
        max_depth: int = benchmark_config.DEFAULT_RANDOM_FOREST_MAX_DEPTH,
        min_samples_split: int = benchmark_config.DEFAULT_RANDOM_FOREST_MIN_SAMPLES_SPLIT,
        min_samples_leaf: int = benchmark_config.DEFAULT_RANDOM_FOREST_MIN_SAMPLES_LEAF,
        max_features_fraction: float = (
            benchmark_config.DEFAULT_RANDOM_FOREST_MAX_FEATURES_FRACTION
        ),
        bootstrap: bool = True,
        random_seed: int = benchmark_config.DEFAULT_RANDOM_SEED,
    ) -> None:
        self._validate_configuration(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            max_features_fraction=max_features_fraction,
        )
        super().__init__(random_seed=random_seed)
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._min_samples_split = min_samples_split
        self._min_samples_leaf = min_samples_leaf
        self._max_features_fraction = max_features_fraction
        self._bootstrap = bootstrap

    @property
    def algorithm_identifier(self) -> str:
        """Return the permanent random-forest regression identity."""

        return benchmark_config.RANDOM_FOREST_ALGORITHM

    @property
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return the immutable forest training configuration."""

        return canonical_metadata(
            {
                "bootstrap": self._bootstrap,
                "max_depth": self._max_depth,
                "max_features_fraction": self._max_features_fraction,
                "min_samples_leaf": self._min_samples_leaf,
                "min_samples_split": self._min_samples_split,
                "n_estimators": self._n_estimators,
                "split_criterion": "squared_error",
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
        master = np.random.default_rng(self.random_seed)
        tree_seeds = master.integers(
            0,
            np.iinfo(np.uint32).max,
            size=self._n_estimators,
            dtype=np.uint32,
        )
        trees: list[BenchmarkTree] = []
        for tree_seed in tree_seeds:
            random = np.random.default_rng(int(tree_seed))
            indices = (
                random.integers(0, features.shape[0], size=features.shape[0])
                if self._bootstrap
                else np.arange(features.shape[0])
            )
            root = self._build_node(
                features[indices],
                targets[indices],
                depth=0,
                random=random,
            )
            trees.append(BenchmarkTree(root=root))
        return self._artifact(
            request=request,
            model_id=model_id,
            trees=tuple(trees),
        )

    def _build_node(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        *,
        depth: int,
        random: np.random.Generator,
    ) -> BenchmarkTreeNode:
        prediction = tuple(float(value) for value in targets.mean(axis=0))
        if (
            depth >= self._max_depth
            or features.shape[0] < self._min_samples_split
            or np.all(targets == targets[0])
        ):
            return BenchmarkTreeNode(prediction=prediction)
        split = self._best_split(features, targets, random)
        if split is None:
            return BenchmarkTreeNode(prediction=prediction)
        feature_index, threshold, left_mask = split
        return BenchmarkTreeNode(
            prediction=prediction,
            feature_index=feature_index,
            threshold=threshold,
            left=self._build_node(
                features[left_mask],
                targets[left_mask],
                depth=depth + 1,
                random=random,
            ),
            right=self._build_node(
                features[~left_mask],
                targets[~left_mask],
                depth=depth + 1,
                random=random,
            ),
        )

    def _best_split(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        random: np.random.Generator,
    ) -> tuple[int, float, np.ndarray] | None:
        feature_count = features.shape[1]
        candidate_count = max(
            1,
            min(
                feature_count,
                math.ceil(self._max_features_fraction * feature_count),
            ),
        )
        feature_indices = tuple(
            sorted(
                int(index)
                for index in random.choice(
                    feature_count,
                    size=candidate_count,
                    replace=False,
                )
            )
        )
        best: tuple[float, int, float, np.ndarray] | None = None
        for feature_index in feature_indices:
            values = np.unique(features[:, feature_index])
            for lower, upper in zip(values[:-1], values[1:]):
                threshold = float(lower + (upper - lower) / 2.0)
                left_mask = features[:, feature_index] <= threshold
                left_count = int(left_mask.sum())
                right_count = features.shape[0] - left_count
                if (
                    left_count < self._min_samples_leaf
                    or right_count < self._min_samples_leaf
                ):
                    continue
                loss = self._squared_error(targets[left_mask]) + self._squared_error(
                    targets[~left_mask]
                )
                candidate = (loss, feature_index, threshold, left_mask)
                if best is None or candidate[:3] < best[:3]:
                    best = candidate
        if best is None:
            return None
        return best[1], best[2], best[3]

    @staticmethod
    def _squared_error(targets: np.ndarray) -> float:
        centered = targets - targets.mean(axis=0)
        return float(np.sum(centered * centered))

    @staticmethod
    def _validate_configuration(
        *,
        n_estimators: int,
        max_depth: int,
        min_samples_split: int,
        min_samples_leaf: int,
        max_features_fraction: float,
    ) -> None:
        if n_estimators < 1:
            raise BenchmarkConfigurationError("Random Forest requires at least one tree.")
        if max_depth < 1:
            raise BenchmarkConfigurationError("Random Forest max_depth must be positive.")
        if max_depth > benchmark_config.MAXIMUM_RANDOM_FOREST_MAX_DEPTH:
            raise BenchmarkConfigurationError(
                "Random Forest max_depth exceeds the supported deterministic limit."
            )
        if min_samples_split < 2:
            raise BenchmarkConfigurationError(
                "Random Forest min_samples_split must be at least two."
            )
        if min_samples_leaf < 1:
            raise BenchmarkConfigurationError(
                "Random Forest min_samples_leaf must be positive."
            )
        if not math.isfinite(max_features_fraction) or not (
            0 < max_features_fraction <= 1
        ):
            raise BenchmarkConfigurationError(
                "Random Forest max_features_fraction must be in (0, 1]."
            )
