"""Immutable contracts for reproducible, model-independent experiment orchestration."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataset_builder.contracts import (
    DatasetSplit,
    NumericValue,
    TrainingExample,
    VersionedTrainingDataset,
)
from app.evaluation.contracts import EvaluationReport, PredictionRow

_SAFE_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


class ExperimentLifecycleState(str, Enum):
    """Recorded lifecycle states for append-only experiment history."""

    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class MetadataValue(BaseModel):
    """One immutable scalar configuration, environment, or execution value."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    value: str | int | float | bool | None

    @field_validator("value")
    @classmethod
    def validate_finite_float(
        cls,
        value: str | int | float | bool | None,
    ) -> str | int | float | bool | None:
        """Reject non-finite metadata because it has no canonical JSON identity."""

        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Experiment metadata floats must be finite.")
        return value


class ExperimentCreationMetadata(BaseModel):
    """Human and temporal creation context recorded with an immutable spec."""

    model_config = ConfigDict(frozen=True)

    created_at: datetime
    created_by: str = Field(min_length=1)
    source: str = Field(default="offline", min_length=1)


class ExperimentSpec(BaseModel):
    """Complete immutable declaration of one offline training experiment."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str = Field(pattern=_SAFE_IDENTIFIER_PATTERN)
    configuration_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    dataset_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    feature_schema_version: str = Field(min_length=1)
    target_schema_version: str = Field(min_length=1)
    evaluation_framework_version: str = Field(min_length=1)
    evaluation_split: DatasetSplit
    algorithm_identifier: str = Field(min_length=1)
    hyperparameters: tuple[MetadataValue, ...] = ()
    random_seed: int
    notes: str | None = None
    creation_metadata: ExperimentCreationMetadata

    @field_validator("hyperparameters")
    @classmethod
    def validate_hyperparameters(cls, values: tuple[MetadataValue, ...]) -> tuple[MetadataValue, ...]:
        """Require deterministic, non-duplicated hyperparameter keys."""

        names = tuple(value.name for value in values)
        if len(set(names)) != len(names):
            raise ValueError("Experiment hyperparameter names must be unique.")
        if names != tuple(sorted(names)):
            raise ValueError("Experiment hyperparameters must use deterministic name ordering.")
        return values

    @field_validator("configuration_hash")
    @classmethod
    def normalize_configuration_hash(cls, value: str) -> str:
        """Use one lowercase representation for indexing identical configurations."""

        return value.lower()

    @field_validator("evaluation_split")
    @classmethod
    def validate_evaluation_split(cls, value: DatasetSplit) -> DatasetSplit:
        """Keep training labels available while holding out evaluation targets."""

        if value is DatasetSplit.TRAIN:
            raise ValueError("Experiment evaluation split must be validation or test.")
        return value

    @model_validator(mode="after")
    def validate_configuration_hash(self) -> "ExperimentSpec":
        """Bind the declared hash to every scientifically relevant configuration field."""

        expected = self.calculate_configuration_hash(
            dataset_checksum=self.dataset_checksum,
            feature_schema_version=self.feature_schema_version,
            target_schema_version=self.target_schema_version,
            evaluation_framework_version=self.evaluation_framework_version,
            evaluation_split=self.evaluation_split,
            algorithm_identifier=self.algorithm_identifier,
            hyperparameters=self.hyperparameters,
            random_seed=self.random_seed,
        )
        if self.configuration_hash.lower() != expected:
            raise ValueError("Experiment configuration hash does not match its configuration.")
        return self

    @classmethod
    def create(
        cls,
        *,
        experiment_id: str,
        dataset_id: str,
        dataset_version: str,
        dataset_checksum: str,
        feature_schema_version: str,
        target_schema_version: str,
        evaluation_framework_version: str,
        evaluation_split: DatasetSplit,
        algorithm_identifier: str,
        hyperparameters: tuple[MetadataValue, ...],
        random_seed: int,
        creation_metadata: ExperimentCreationMetadata,
        notes: str | None = None,
    ) -> "ExperimentSpec":
        """Create a spec with a validated deterministic configuration hash."""

        configuration_hash = cls.calculate_configuration_hash(
            dataset_checksum=dataset_checksum,
            feature_schema_version=feature_schema_version,
            target_schema_version=target_schema_version,
            evaluation_framework_version=evaluation_framework_version,
            evaluation_split=evaluation_split,
            algorithm_identifier=algorithm_identifier,
            hyperparameters=hyperparameters,
            random_seed=random_seed,
        )
        return cls(
            experiment_id=experiment_id,
            configuration_hash=configuration_hash,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            dataset_checksum=dataset_checksum,
            feature_schema_version=feature_schema_version,
            target_schema_version=target_schema_version,
            evaluation_framework_version=evaluation_framework_version,
            evaluation_split=evaluation_split,
            algorithm_identifier=algorithm_identifier,
            hyperparameters=hyperparameters,
            random_seed=random_seed,
            notes=notes,
            creation_metadata=creation_metadata,
        )

    @staticmethod
    def calculate_configuration_hash(
        *,
        dataset_checksum: str,
        feature_schema_version: str,
        target_schema_version: str,
        evaluation_framework_version: str,
        evaluation_split: DatasetSplit,
        algorithm_identifier: str,
        hyperparameters: tuple[MetadataValue, ...],
        random_seed: int,
    ) -> str:
        """Return the canonical identity of a scientifically equivalent configuration."""

        payload = {
            "algorithm_identifier": algorithm_identifier,
            "dataset_checksum": dataset_checksum.lower(),
            "evaluation_framework_version": evaluation_framework_version,
            "evaluation_split": evaluation_split.value,
            "feature_schema_version": feature_schema_version,
            "hyperparameters": [
                value.model_dump(mode="json") for value in hyperparameters
            ],
            "random_seed": random_seed,
            "target_schema_version": target_schema_version,
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()


class ArtifactReference(BaseModel):
    """Checksum-addressed local immutable artifact reference."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    media_type: str = Field(default="application/json", min_length=1)


class ModelCompatibility(BaseModel):
    """Explicit candidate compatibility decision against the declared experiment data."""

    model_config = ConfigDict(frozen=True)

    compatible: bool
    reasons: tuple[str, ...] = ()


class ModelCandidate(BaseModel):
    """A model artifact supplied by an adapter, without embedding model logic."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    feature_schema: tuple[str, ...] = Field(min_length=1)
    target_schema: tuple[str, ...] = Field(min_length=1)
    artifact_reference: ArtifactReference
    compatibility: ModelCompatibility


class ModelInputRow(BaseModel):
    """Feature-only held-out row exposed to a model adapter for prediction."""

    model_config = ConfigDict(frozen=True)

    example_id: str = Field(min_length=1)
    player_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    features: tuple[NumericValue, ...] = Field(min_length=1)


class ModelExecutionRequest(BaseModel):
    """Immutable data boundary supplied to an algorithm-specific adapter."""

    model_config = ConfigDict(frozen=True)

    spec: ExperimentSpec
    dataset: VersionedTrainingDataset
    training_examples: tuple[TrainingExample, ...] = Field(min_length=1)
    validation_examples: tuple[TrainingExample, ...] = ()
    prediction_inputs: tuple[ModelInputRow, ...] = Field(min_length=1)


class ModelAdapterOutput(BaseModel):
    """Algorithm-neutral output collected from a model adapter."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    feature_schema: tuple[str, ...] = Field(min_length=1)
    target_schema: tuple[str, ...] = Field(min_length=1)
    model_artifact: bytes = Field(min_length=1)
    model_artifact_media_type: str = Field(
        default="application/octet-stream",
        min_length=1,
    )
    prediction_rows: tuple[PredictionRow, ...] = ()
    execution_metadata: tuple[MetadataValue, ...] = ()

    @model_validator(mode="after")
    def validate_deterministic_output(self) -> "ModelAdapterOutput":
        """Require deterministic row and metadata ordering from every adapter."""

        prediction_keys = tuple(
            (row.example_id, row.target_name) for row in self.prediction_rows
        )
        if prediction_keys != tuple(sorted(prediction_keys)):
            raise ValueError("Adapter predictions must use deterministic identity ordering.")
        metadata_names = tuple(value.name for value in self.execution_metadata)
        if (
            len(set(metadata_names)) != len(metadata_names)
            or metadata_names != tuple(sorted(metadata_names))
        ):
            raise ValueError("Adapter execution metadata must have unique, sorted names.")
        return self


class ExecutionEnvironment(BaseModel):
    """Software and dependency snapshot for a concrete adapter execution."""

    model_config = ConfigDict(frozen=True)

    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    application_version: str = Field(min_length=1)
    dependency_versions: tuple[MetadataValue, ...]

    @field_validator("dependency_versions")
    @classmethod
    def validate_dependency_versions(
        cls,
        values: tuple[MetadataValue, ...],
    ) -> tuple[MetadataValue, ...]:
        """Require one deterministically ordered version per dependency."""

        names = tuple(value.name for value in values)
        if len(set(names)) != len(names) or names != tuple(sorted(names)):
            raise ValueError("Dependency versions must have unique, sorted names.")
        return values


class ExperimentRun(BaseModel):
    """One immutable lifecycle event retained by the experiment registry."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    experiment_id: str = Field(pattern=_SAFE_IDENTIFIER_PATTERN)
    configuration_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    attempt: int = Field(ge=1)
    state: ExperimentLifecycleState
    started_at: datetime
    ended_at: datetime | None = None
    recovered_from_run_id: str | None = None
    environment: ExecutionEnvironment
    artifact_references: tuple[ArtifactReference, ...] = ()
    execution_metadata: tuple[MetadataValue, ...] = ()


class ExecutionSummary(BaseModel):
    """Adapter execution outcome retained separately from deterministic result identity."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    started_at: datetime
    completed_at: datetime
    environment: ExecutionEnvironment
    execution_metadata: tuple[MetadataValue, ...] = ()


class PromotionRecommendation(BaseModel):
    """Evaluation-derived recommendation; it never promotes a candidate itself."""

    model_config = ConfigDict(frozen=True)

    eligible: bool
    reasons: tuple[str, ...]


class ExperimentProvenance(BaseModel):
    """Lineage linking result evidence to the dataset and evaluation report."""

    model_config = ConfigDict(frozen=True)

    framework_schema_version: str = Field(min_length=1)
    configuration_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    dataset_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    evaluation_report_id: str = Field(min_length=1)
    evaluation_report_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    model_artifact_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class ExperimentResult(BaseModel):
    """Immutable offline experiment result combining declared and observed evidence."""

    model_config = ConfigDict(frozen=True)

    result_id: str = Field(min_length=1)
    spec: ExperimentSpec
    model_candidate: ModelCandidate
    evaluation_report: EvaluationReport
    execution_summary: ExecutionSummary
    promotion_recommendation: PromotionRecommendation
    warnings: tuple[str, ...] = ()
    artifact_references: tuple[ArtifactReference, ...]
    provenance: ExperimentProvenance
    reproducibility_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class ExperimentComparison(BaseModel):
    """Immutable comparison of completed experiment results; no promotion action occurs."""

    model_config = ConfigDict(frozen=True)

    comparison_id: str = Field(min_length=1)
    experiment_ids: tuple[str, ...] = Field(min_length=2)
    recommended_experiment_id: str | None = None
    rationale: str = Field(min_length=1)
    checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_experiment_ids(self) -> "ExperimentComparison":
        """Require every compared experiment identifier exactly once."""

        if len(set(self.experiment_ids)) != len(self.experiment_ids):
            raise ValueError("Comparison experiment IDs must be unique.")
        if (
            self.recommended_experiment_id is not None
            and self.recommended_experiment_id not in self.experiment_ids
        ):
            raise ValueError("Comparison recommendation must reference a compared experiment.")
        return self
