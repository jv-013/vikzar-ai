"""Immutable, algorithm-independent contracts for scientific model evaluation."""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataset_builder.contracts import DatasetSplit


class SliceDimension(str, Enum):
    """Supported evidence dimensions for stratified performance reporting."""

    PLAYER = "player"
    POSITION = "position"
    DRILL = "drill"
    SESSION = "session"
    DATASET_SPLIT = "dataset_split"


class EvaluationSlice(BaseModel):
    """One named subset of the evaluated Phase 3 evidence."""

    model_config = ConfigDict(frozen=True)

    dimension: SliceDimension
    value: str = Field(min_length=1)


class PredictionProvenance(BaseModel):
    """Phase 3 lineage bound to a model's submitted prediction set."""

    model_config = ConfigDict(frozen=True)

    dataset_schema_version: str = Field(min_length=1)
    dataset_manifest_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    dataset_created_at: datetime
    feature_schema_names: tuple[str, ...] = Field(min_length=1)
    target_names: tuple[str, ...] = Field(min_length=1)

    @field_validator("feature_schema_names", "target_names")
    @classmethod
    def validate_schema_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require the submitted schema to remain explicit and ordered."""

        if any(not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError("Prediction provenance schema names must be non-empty and unique.")
        return values


class GroundTruthRow(BaseModel):
    """One direct measured Phase 3 target with non-feature slicing context."""

    model_config = ConfigDict(frozen=True)

    example_id: str = Field(min_length=1)
    target_name: str = Field(min_length=1)
    value: float
    player_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    dataset_split: DatasetSplit
    position: str | None = None
    drill_id: str | None = None

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: float) -> float:
        """Reject non-finite ground-truth values instead of altering them."""

        if not math.isfinite(value):
            raise ValueError("Ground-truth values must be finite.")
        return value


class PredictionRow(BaseModel):
    """One unmodified model prediction aligned by example and target identity."""

    model_config = ConfigDict(frozen=True)

    example_id: str = Field(min_length=1)
    target_name: str = Field(min_length=1)
    value: float
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: float) -> float:
        """Reject non-finite prediction values; evaluation never repairs them."""

        if not math.isfinite(value):
            raise ValueError("Prediction values must be finite.")
        return value


class PredictionSet(BaseModel):
    """Immutable submitted predictions and Phase 3 direct-measurement truth."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    split_id: DatasetSplit
    prediction_rows: tuple[PredictionRow, ...] = ()
    ground_truth_rows: tuple[GroundTruthRow, ...] = ()
    provenance: PredictionProvenance

    @model_validator(mode="after")
    def validate_identity_alignment(self) -> "PredictionSet":
        """Require unique rows and reject predictions outside submitted truth."""

        truth_keys = [(row.example_id, row.target_name) for row in self.ground_truth_rows]
        prediction_keys = [(row.example_id, row.target_name) for row in self.prediction_rows]
        if len(set(truth_keys)) != len(truth_keys):
            raise ValueError("Ground-truth rows must be unique per example and target.")
        if len(set(prediction_keys)) != len(prediction_keys):
            raise ValueError("Prediction rows must be unique per example and target.")
        if not set(prediction_keys).issubset(truth_keys):
            raise ValueError("Predictions must reference submitted ground-truth rows.")
        if any(row.dataset_split is not self.split_id for row in self.ground_truth_rows):
            raise ValueError("Ground-truth rows must belong to PredictionSet.split_id.")
        if any(row.target_name not in self.provenance.target_names for row in self.ground_truth_rows):
            raise ValueError("Ground-truth target names must belong to Phase 3 target schema.")
        return self


class MetricResult(BaseModel):
    """Performance metrics for one target over all or one explicit slice."""

    model_config = ConfigDict(frozen=True)

    target_name: str = Field(min_length=1)
    slice: EvaluationSlice | None = None
    mae: float | None = Field(default=None, ge=0)
    rmse: float | None = Field(default=None, ge=0)
    r_squared: float | None = None
    pearson_correlation: float | None = Field(default=None, ge=-1, le=1)
    bias: float | None = None
    coverage: float = Field(ge=0, le=1)
    sample_count: int = Field(ge=0)
    missing_prediction_count: int = Field(ge=0)


class CalibrationResult(BaseModel):
    """Confidence reliability summary for one target and optional slice."""

    model_config = ConfigDict(frozen=True)

    target_name: str = Field(min_length=1)
    slice: EvaluationSlice | None = None
    available: bool
    confidence_sample_count: int = Field(ge=0)
    mean_confidence: float | None = Field(default=None, ge=0, le=1)
    empirical_agreement: float | None = Field(default=None, ge=0, le=1)
    calibration_gap: float | None = Field(default=None, ge=0, le=1)


class ReleaseGatePolicy(BaseModel):
    """Configurable, model-external rules for release eligibility."""

    model_config = ConfigDict(frozen=True)

    minimum_r_squared: float | None = None
    maximum_rmse: float | None = Field(default=None, ge=0)
    minimum_sample_count: int = Field(default=1, ge=1)
    require_complete_predictions: bool = True


class ReleaseGateResult(BaseModel):
    """One explainable pass/fail outcome from an external release policy."""

    model_config = ConfigDict(frozen=True)

    gate_name: str = Field(min_length=1)
    target_name: str | None = None
    passed: bool
    observed_value: float | int | None = None
    threshold: float | int | None = None
    message: str = Field(min_length=1)


class EvaluationProvenance(BaseModel):
    """Immutable model, dataset, policy, and schema lineage for one report."""

    model_config = ConfigDict(frozen=True)

    evaluation_schema_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    dataset_schema_version: str = Field(min_length=1)
    dataset_manifest_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    split_id: DatasetSplit
    feature_schema_names: tuple[str, ...]
    target_names: tuple[str, ...]


class EvaluationReport(BaseModel):
    """Immutable, checksum-bound performance evidence for a submitted model."""

    model_config = ConfigDict(frozen=True)

    report_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    evaluated_at: datetime
    overall_metrics: tuple[MetricResult, ...]
    sliced_metrics: tuple[MetricResult, ...]
    calibration: tuple[CalibrationResult, ...]
    warnings: tuple[str, ...]
    failed_checks: tuple[str, ...]
    gate_results: tuple[ReleaseGateResult, ...]
    release_approved: bool
    gate_policy: ReleaseGatePolicy
    provenance: EvaluationProvenance
    report_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
