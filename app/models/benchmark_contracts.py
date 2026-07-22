"""Immutable, versioned contracts for deterministic benchmark model artifacts."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import benchmark_config
from app.experiments.contracts import MetadataValue


class BenchmarkTreeNode(BaseModel):
    """One immutable multi-output regression-tree node."""

    model_config = ConfigDict(frozen=True)

    prediction: tuple[float, ...] = Field(min_length=1)
    feature_index: int | None = Field(default=None, ge=0)
    threshold: float | None = None
    left: "BenchmarkTreeNode | None" = None
    right: "BenchmarkTreeNode | None" = None

    @field_validator("prediction")
    @classmethod
    def validate_prediction(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        """Reject non-finite leaf or fallback predictions."""

        if any(not math.isfinite(value) for value in values):
            raise ValueError("Tree predictions must be finite.")
        return values

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, value: float | None) -> float | None:
        """Reject non-finite split thresholds."""

        if value is not None and not math.isfinite(value):
            raise ValueError("Tree thresholds must be finite.")
        return value

    @model_validator(mode="after")
    def validate_node_shape(self) -> "BenchmarkTreeNode":
        """Require either a complete leaf or a complete binary split."""

        split_values = (self.feature_index, self.threshold, self.left, self.right)
        populated = tuple(value is not None for value in split_values)
        if any(populated) and not all(populated):
            raise ValueError("Tree nodes must be complete leaves or complete binary splits.")
        return self


class BenchmarkTree(BaseModel):
    """One immutable tree within a deterministic regression forest."""

    model_config = ConfigDict(frozen=True)

    root: BenchmarkTreeNode


class BenchmarkModelArtifact(BaseModel):
    """Canonical predictive state for one permanent benchmark model."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(
        default=benchmark_config.BENCHMARK_MODEL_SCHEMA_VERSION,
        min_length=1,
    )
    algorithm_identifier: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    configuration_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    random_seed: int
    feature_schema: tuple[str, ...] = Field(min_length=1)
    target_schema: tuple[str, ...] = Field(min_length=1)
    hyperparameters: tuple[MetadataValue, ...]
    constant_values: tuple[float, ...] = ()
    coefficients: tuple[tuple[float, ...], ...] = ()
    intercepts: tuple[float, ...] = ()
    trees: tuple[BenchmarkTree, ...] = ()

    @field_validator("constant_values", "intercepts")
    @classmethod
    def validate_finite_vector(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        """Require finite serialized numeric state."""

        if any(not math.isfinite(value) for value in values):
            raise ValueError("Serialized benchmark values must be finite.")
        return values

    @field_validator("feature_schema", "target_schema")
    @classmethod
    def validate_ordered_schema(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require explicit unique names while preserving Phase 3 ordering."""

        if any(not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError("Benchmark schemas must contain unique non-empty names.")
        return values

    @field_validator("hyperparameters")
    @classmethod
    def validate_hyperparameters(
        cls,
        values: tuple[MetadataValue, ...],
    ) -> tuple[MetadataValue, ...]:
        """Require canonical immutable hyperparameter ordering in stored artifacts."""

        names = tuple(value.name for value in values)
        if len(set(names)) != len(names) or names != tuple(sorted(names)):
            raise ValueError("Benchmark hyperparameters must have unique, sorted names.")
        return values

    @field_validator("coefficients")
    @classmethod
    def validate_finite_matrix(
        cls,
        values: tuple[tuple[float, ...], ...],
    ) -> tuple[tuple[float, ...], ...]:
        """Require finite serialized coefficient matrices."""

        if any(not math.isfinite(value) for row in values for value in row):
            raise ValueError("Serialized benchmark coefficients must be finite.")
        return values

    @model_validator(mode="after")
    def validate_algorithm_payload(self) -> "BenchmarkModelArtifact":
        """Bind each algorithm identifier to exactly one predictive payload shape."""

        target_count = len(self.target_schema)
        feature_count = len(self.feature_schema)
        if self.schema_version != benchmark_config.BENCHMARK_MODEL_SCHEMA_VERSION:
            raise ValueError("Unsupported benchmark model schema version.")
        if self.model_version != self.schema_version:
            raise ValueError("Benchmark model version must match its artifact schema version.")
        expected_model_id = (
            f"{self.algorithm_identifier}-{self.configuration_hash[:24]}"
        )
        if self.model_id != expected_model_id:
            raise ValueError("Benchmark model ID does not match its immutable configuration.")
        if self.algorithm_identifier == benchmark_config.DUMMY_MEAN_ALGORITHM:
            valid = (
                len(self.constant_values) == target_count
                and not self.coefficients
                and not self.intercepts
                and not self.trees
            )
        elif self.algorithm_identifier in {
            benchmark_config.LINEAR_REGRESSION_ALGORITHM,
            benchmark_config.RIDGE_REGRESSION_ALGORITHM,
        }:
            valid = (
                len(self.coefficients) == target_count
                and all(len(row) == feature_count for row in self.coefficients)
                and len(self.intercepts) == target_count
                and not self.constant_values
                and not self.trees
            )
        elif self.algorithm_identifier == benchmark_config.RANDOM_FOREST_ALGORITHM:
            valid = (
                bool(self.trees)
                and not self.constant_values
                and not self.coefficients
                and not self.intercepts
                and self._tree_dimensions_are_valid(self.trees, feature_count, target_count)
            )
        else:
            raise ValueError("Unsupported benchmark algorithm identifier.")
        if not valid:
            raise ValueError("Benchmark artifact payload does not match its algorithm.")
        return self

    @staticmethod
    def _tree_dimensions_are_valid(
        trees: tuple[BenchmarkTree, ...],
        feature_count: int,
        target_count: int,
    ) -> bool:
        pending = [tree.root for tree in trees]
        while pending:
            node = pending.pop()
            if len(node.prediction) != target_count:
                return False
            if node.feature_index is not None:
                if node.feature_index >= feature_count or node.left is None or node.right is None:
                    return False
                pending.extend((node.left, node.right))
        return True
