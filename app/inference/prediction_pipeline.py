"""Vectorized deterministic prediction pipeline for one approved model."""

from __future__ import annotations

from .configuration import InferenceRuntimeConfig
from .contracts import (
    InferenceMetadata,
    InferencePrediction,
    InferenceRequest,
    PredictionValue,
)
from .model_loader import LoadedInferenceModel
from .validation import InferenceInputValidator, InferenceOutputValidator


class PredictionPipeline:
    """Validate, predict once per batch, and build immutable output evidence."""

    def __init__(
        self,
        model: LoadedInferenceModel,
        config: InferenceRuntimeConfig,
    ) -> None:
        self._model = model
        self._config = config
        self._input_validator = InferenceInputValidator(config)

    def predict(
        self,
        requests: tuple[InferenceRequest, ...],
    ) -> tuple[InferencePrediction, ...]:
        """Return ordered deterministic predictions for an immutable request batch."""

        features = self._input_validator.matrix(requests, self._model)
        raw_predictions = self._model.predictor.predict(features)
        predictions = InferenceOutputValidator.validate(
            raw_predictions,
            row_count=len(requests),
            target_count=len(self._model.target_schema),
        )
        artifact = self._model.predictor.artifact
        return tuple(
            InferencePrediction.create(
                predictions=tuple(
                    PredictionValue(
                        target_name=target_name,
                        value=float(predictions[row_index, target_index]),
                    )
                    for target_index, target_name in enumerate(
                        self._model.target_schema
                    )
                ),
                metadata=InferenceMetadata(
                    model_id=artifact.model_id,
                    model_version=artifact.model_version,
                    model_checksum=self._model.registration.model_artifact.sha256,
                    model_configuration_hash=artifact.configuration_hash,
                    registration_id=self._model.registration.registration_id,
                    selection_id=self._model.selection.selection_id,
                    inference_configuration_hash=self._config.configuration_hash,
                    source_feature_vector_id=request.feature_vector.feature_vector_id,
                    source_schema_version=request.feature_vector.schema_version,
                    source_timestamp=request.feature_vector.timestamp,
                    player_id=request.feature_vector.player.player_id,
                    session_id=request.feature_vector.session.session_id,
                    group_id=request.group_id,
                    window_start=request.feature_vector.groups[
                        request.group_id
                    ].window_start,
                    window_end=request.feature_vector.groups[
                        request.group_id
                    ].window_end,
                    feature_schema=self._model.feature_schema,
                    target_schema=self._model.target_schema,
                ),
            )
            for row_index, request in enumerate(requests)
        )
