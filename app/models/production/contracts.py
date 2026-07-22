"""Immutable contracts for versioned production model artifacts and lifecycle evidence."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import production_model_config
from app.experiments.contracts import (
    ArtifactReference,
    ExperimentComparison,
    ExperimentResult,
    MetadataValue,
)


class ProductionLayer(BaseModel):
    """One immutable dense layer with row-major weights and output biases."""

    model_config = ConfigDict(frozen=True)

    weights: tuple[tuple[float, ...], ...] = Field(min_length=1)
    biases: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "ProductionLayer":
        """Require a rectangular finite matrix matching its bias width."""

        widths = {len(row) for row in self.weights}
        if widths != {len(self.biases)}:
            raise ValueError("Production layer weights must match bias dimensions.")
        if any(
            not math.isfinite(value)
            for row in self.weights
            for value in row
        ) or any(not math.isfinite(value) for value in self.biases):
            raise ValueError("Production layer values must be finite.")
        return self


class ProductionTrainingSummary(BaseModel):
    """Deterministic training observations retained with the model state."""

    model_config = ConfigDict(frozen=True)

    selected_epoch: int = Field(ge=1)
    training_loss: float = Field(ge=0)
    validation_loss: float | None = Field(default=None, ge=0)
    training_example_count: int = Field(ge=1)
    validation_example_count: int = Field(ge=0)


class ProductionModelArtifact(BaseModel):
    """Platform-independent predictive state for the permanent production MLP."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = production_model_config.PRODUCTION_MODEL_SCHEMA_VERSION
    algorithm_identifier: str = production_model_config.PRODUCTION_MODEL_ALGORITHM
    model_id: str = Field(min_length=1)
    model_version: str = production_model_config.PRODUCTION_MODEL_SCHEMA_VERSION
    configuration_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    random_seed: int
    feature_schema: tuple[str, ...] = Field(min_length=1)
    target_schema: tuple[str, ...] = Field(min_length=1)
    hyperparameters: tuple[MetadataValue, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    target_mean: tuple[float, ...]
    target_scale: tuple[float, ...]
    layers: tuple[ProductionLayer, ...] = Field(min_length=2)
    training_summary: ProductionTrainingSummary

    @field_validator(
        "feature_mean",
        "feature_scale",
        "target_mean",
        "target_scale",
    )
    @classmethod
    def validate_finite_vector(cls, values: tuple[float, ...]) -> tuple[float, ...]:
        """Require finite normalization state."""

        if any(not math.isfinite(value) for value in values):
            raise ValueError("Production normalization values must be finite.")
        return values

    @model_validator(mode="after")
    def validate_artifact(self) -> "ProductionModelArtifact":
        """Bind version, schemas, normalization, layers, and identity."""

        if (
            self.schema_version != production_model_config.PRODUCTION_MODEL_SCHEMA_VERSION
            or self.model_version != self.schema_version
            or self.algorithm_identifier
            != production_model_config.PRODUCTION_MODEL_ALGORITHM
        ):
            raise ValueError("Unsupported production model artifact version or algorithm.")
        expected_id = (
            f"{self.algorithm_identifier}-{self.configuration_hash[:24]}"
        )
        if self.model_id != expected_id:
            raise ValueError("Production model ID does not match its configuration.")
        feature_count = len(self.feature_schema)
        target_count = len(self.target_schema)
        if (
            len(self.feature_mean) != feature_count
            or len(self.feature_scale) != feature_count
            or len(self.target_mean) != target_count
            or len(self.target_scale) != target_count
            or any(value <= 0 for value in self.feature_scale + self.target_scale)
        ):
            raise ValueError("Production normalization dimensions are invalid.")
        dimensions = [feature_count]
        dimensions.extend(len(layer.biases) for layer in self.layers)
        if dimensions[-1] != target_count:
            raise ValueError("Production output layer does not match target schema.")
        if any(
            len(layer.weights) != dimensions[index]
            for index, layer in enumerate(self.layers)
        ):
            raise ValueError("Production layer chain dimensions are invalid.")
        names = tuple(value.name for value in self.hyperparameters)
        if len(set(names)) != len(names) or names != tuple(sorted(names)):
            raise ValueError("Production hyperparameters must be unique and ordered.")
        return self


class ProductionModelRegistration(BaseModel):
    """Immutable registry entry linking a model to Phase 5 and Phase 4 evidence."""

    model_config = ConfigDict(frozen=True)

    registration_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    configuration_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    dataset_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    model_artifact: ArtifactReference
    evaluation_report_id: str = Field(min_length=1)
    evaluation_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    reproducibility_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class ProductionModelSelection(BaseModel):
    """Metric-authority-preserving comparison against all Phase 6 benchmarks."""

    model_config = ConfigDict(frozen=True)

    selection_id: str = Field(min_length=1)
    production_experiment_id: str = Field(min_length=1)
    benchmark_experiment_ids: tuple[str, ...] = Field(min_length=4)
    comparison: ExperimentComparison
    production_recommended: bool
    rationale: str = Field(min_length=1)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProductionTrainingOutcome(BaseModel):
    """Complete immutable outcome of production training and benchmark selection."""

    model_config = ConfigDict(frozen=True)

    experiment_result: ExperimentResult
    registration: ProductionModelRegistration
    selection: ProductionModelSelection
    registration_artifact: ArtifactReference
    selection_artifact: ArtifactReference
