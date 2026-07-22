"""Immutable contracts for reproducible supervised training datasets."""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DatasetSplit(str, Enum):
    """Named non-overlapping partitions of a supervised dataset."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class DatasetSplitPolicy(BaseModel):
    """Deterministic player/session-grouped split policy."""

    model_config = ConfigDict(frozen=True)

    train_fraction: float = Field(default=0.7, gt=0, le=1)
    validation_fraction: float = Field(default=0.15, ge=0, le=1)
    test_fraction: float = Field(default=0.15, ge=0, le=1)
    seed: str = Field(default="vikzar-dataset-v1", min_length=1)

    @model_validator(mode="after")
    def validate_fractions(self) -> "DatasetSplitPolicy":
        """Require the declared split fractions to cover exactly one dataset."""

        total = self.train_fraction + self.validation_fraction + self.test_fraction
        if not math.isclose(total, 1.0, abs_tol=1e-9):
            raise ValueError("Dataset split fractions must sum to 1.0.")
        return self


class DatasetBuildSpec(BaseModel):
    """The immutable policy used to derive one versioned dataset."""

    model_config = ConfigDict(frozen=True)

    dataset_name: str = Field(min_length=1)
    target_metric_names: tuple[str, ...] = Field(min_length=1)
    included_feature_domains: tuple[str, ...] = Field(default=("motion", "pressure"), min_length=1)
    split_policy: DatasetSplitPolicy = Field(default_factory=DatasetSplitPolicy)

    @field_validator("target_metric_names", "included_feature_domains")
    @classmethod
    def validate_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require non-empty, non-duplicated stable names."""

        if any(not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError("Dataset build names must be non-empty and unique.")
        return values

    @field_validator("included_feature_domains")
    @classmethod
    def validate_feature_domains(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Restrict training features to Smart Pod domains, never EMG targets."""

        unsupported = set(values) - {"motion", "pressure"}
        if unsupported:
            raise ValueError("Only Smart Pod motion and pressure domains may be training features.")
        return values


class NumericValue(BaseModel):
    """One immutable named numeric feature or target value."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    value: float

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: float) -> float:
        """Reject non-finite values rather than silently imputing them."""

        if not math.isfinite(value):
            raise ValueError("Dataset values must be finite.")
        return value


class TrainingExample(BaseModel):
    """One accepted window represented as leakage-safe model input and targets."""

    model_config = ConfigDict(frozen=True)

    example_id: str = Field(min_length=1)
    verified_session_id: str = Field(min_length=1)
    capture_session_id: str = Field(min_length=1)
    player_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    source_feature_vector_id: str = Field(min_length=1)
    aligned_window_id: str = Field(min_length=1)
    split: DatasetSplit
    features: tuple[NumericValue, ...] = Field(min_length=1)
    targets: tuple[NumericValue, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_names(self) -> "TrainingExample":
        """Require exactly one value for every feature and target name."""

        if len({item.name for item in self.features}) != len(self.features):
            raise ValueError("Training example feature names must be unique.")
        if len({item.name for item in self.targets}) != len(self.targets):
            raise ValueError("Training example target names must be unique.")
        return self


class DatasetFeatureSchema(BaseModel):
    """Ordered feature and target columns consumed by later model phases."""

    model_config = ConfigDict(frozen=True)

    feature_names: tuple[str, ...] = Field(min_length=1)
    target_names: tuple[str, ...] = Field(min_length=1)

    @field_validator("feature_names", "target_names")
    @classmethod
    def validate_columns(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require deterministic unique tabular column names."""

        if any(not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError("Feature-schema names must be non-empty and unique.")
        return values


class DatasetSource(BaseModel):
    """Immutable provenance reference to one Phase 2 verified session."""

    model_config = ConfigDict(frozen=True)

    verified_session_id: str = Field(min_length=1)
    capture_session_id: str = Field(min_length=1)
    player_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    source_sha256: tuple["ChecksumEntry", ...]


class ChecksumEntry(BaseModel):
    """One named SHA-256 value preserved as provenance text, never a number."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class DatasetSplitMembership(BaseModel):
    """A player/session group assigned to exactly one split."""

    model_config = ConfigDict(frozen=True)

    player_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    split: DatasetSplit


class VersionedTrainingDataset(BaseModel):
    """Persistable manifest for an immutable, locally stored training dataset."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    created_at: datetime
    build_spec: DatasetBuildSpec
    feature_schema: DatasetFeatureSchema
    sources: tuple[DatasetSource, ...] = Field(min_length=1)
    split_memberships: tuple[DatasetSplitMembership, ...] = Field(min_length=1)
    example_count: int = Field(gt=0)
