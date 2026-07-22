"""Immutable input, evidence, prediction, and metadata contracts for Phase 8."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import inference_config
from app.experiments.contracts import ArtifactReference
from app.schemas.raw_feature_vector import RawFeatureVector
from app.validation.validator import ValidatedRawFeatureVector


class ApprovedModelReferences(BaseModel):
    """Checksum-addressed Phase 7 registration and approval evidence."""

    model_config = ConfigDict(frozen=True)

    registration: ArtifactReference
    selection: ArtifactReference

    @model_validator(mode="after")
    def validate_reference_types(self) -> "ApprovedModelReferences":
        """Require the exact Phase 7 evidence types used by the loader."""

        if self.registration.artifact_type != "production_model_registration":
            raise ValueError("Registration reference is not Phase 7 model evidence.")
        if self.selection.artifact_type != "production_model_selection":
            raise ValueError("Selection reference is not Phase 7 approval evidence.")
        if (
            self.registration.media_type != "application/json"
            or self.selection.media_type != "application/json"
        ):
            raise ValueError("Phase 7 approval evidence must be canonical JSON.")
        return self

    @property
    def cache_key(self) -> str:
        """Return a stable cache key for the exact approval evidence pair."""

        return f"{self.registration.sha256.lower()}:{self.selection.sha256.lower()}"


class InferenceRequest(BaseModel):
    """One trusted runtime feature vector and synchronization group to predict."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    feature_vector: ValidatedRawFeatureVector
    group_id: str = Field(min_length=1)

    @field_validator("feature_vector")
    @classmethod
    def validate_feature_vector_type(
        cls,
        value: ValidatedRawFeatureVector,
    ) -> ValidatedRawFeatureVector:
        """Reject mappings and internal ETL contracts at the Phase 8 boundary."""

        if not isinstance(value, RawFeatureVector):
            raise TypeError("Inference requires a ValidatedRawFeatureVector instance.")
        return value

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        """Reject whitespace-only synchronization group identifiers."""

        if not value.strip():
            raise ValueError("Inference group_id must not be blank.")
        return value


class PredictionValue(BaseModel):
    """One ordered finite model output with no risk interpretation."""

    model_config = ConfigDict(frozen=True)

    target_name: str = Field(min_length=1)
    value: float

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: float) -> float:
        """Reject invalid numerical output at the model boundary."""

        if not math.isfinite(value):
            raise ValueError("Inference predictions must be finite.")
        return value


class InferenceMetadata(BaseModel):
    """Deterministic lineage for one prediction, derived without wall-clock state."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = inference_config.INFERENCE_SCHEMA_VERSION
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    model_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    model_configuration_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    registration_id: str = Field(min_length=1)
    selection_id: str = Field(min_length=1)
    inference_configuration_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    source_feature_vector_id: str = Field(min_length=1)
    source_schema_version: str = Field(min_length=1)
    source_timestamp: datetime
    player_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    window_start: float
    window_end: float
    feature_schema: tuple[str, ...] = Field(min_length=1)
    target_schema: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_metadata(self) -> "InferenceMetadata":
        """Bind metadata to ordered schemas and a valid source window."""

        if (
            self.schema_version != inference_config.INFERENCE_SCHEMA_VERSION
            or self.window_start >= self.window_end
        ):
            raise ValueError("Inference metadata version or window is invalid.")
        if (
            len(set(self.feature_schema)) != len(self.feature_schema)
            or len(set(self.target_schema)) != len(self.target_schema)
        ):
            raise ValueError("Inference metadata schemas must contain unique names.")
        return self


class InferencePrediction(BaseModel):
    """Immutable predictions and lineage returned by the Phase 8 engine."""

    model_config = ConfigDict(frozen=True)

    prediction_id: str = Field(min_length=1)
    predictions: tuple[PredictionValue, ...] = Field(min_length=1)
    metadata: InferenceMetadata
    checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> "InferencePrediction":
        """Verify ordered targets and the content-derived prediction identity."""

        names = tuple(value.target_name for value in self.predictions)
        if names != self.metadata.target_schema:
            raise ValueError("Prediction ordering must match the approved target schema.")
        expected_checksum = self.calculate_checksum(self.predictions, self.metadata)
        if self.checksum.lower() != expected_checksum:
            raise ValueError("Inference prediction checksum does not match its content.")
        if self.prediction_id != f"prediction-{expected_checksum[:24]}":
            raise ValueError("Inference prediction ID does not match its content.")
        return self

    @classmethod
    def create(
        cls,
        *,
        predictions: tuple[PredictionValue, ...],
        metadata: InferenceMetadata,
    ) -> "InferencePrediction":
        """Create a prediction with a deterministic checksum and identifier."""

        checksum = cls.calculate_checksum(predictions, metadata)
        return cls(
            prediction_id=f"prediction-{checksum[:24]}",
            predictions=predictions,
            metadata=metadata,
            checksum=checksum,
        )

    @staticmethod
    def calculate_checksum(
        predictions: tuple[PredictionValue, ...],
        metadata: InferenceMetadata,
    ) -> str:
        """Hash canonical output content without non-deterministic runtime state."""

        payload = {
            "metadata": metadata.model_dump(mode="json"),
            "predictions": [
                prediction.model_dump(mode="json") for prediction in predictions
            ],
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
