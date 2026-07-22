"""Public low-latency runtime facade for deterministic Phase 8 inference."""

from __future__ import annotations

from collections.abc import Sequence

from app.experiments.artifact_store import ExperimentArtifactStore
from app.validation.validator import ValidatedRawFeatureVector

from .configuration import InferenceRuntimeConfig
from .contracts import ApprovedModelReferences, InferencePrediction, InferenceRequest
from .exceptions import InferenceInputError
from .model_loader import ApprovedProductionModelLoader
from .prediction_pipeline import PredictionPipeline


class InferenceEngine:
    """Reuse one approved model for single and vectorized batch prediction."""

    def __init__(
        self,
        artifact_store: ExperimentArtifactStore,
        references: ApprovedModelReferences,
        *,
        config: InferenceRuntimeConfig | None = None,
        loader: ApprovedProductionModelLoader | None = None,
    ) -> None:
        self._config = config or InferenceRuntimeConfig()
        model_loader = loader or ApprovedProductionModelLoader(
            artifact_store,
            config=self._config,
        )
        self._model = model_loader.load(references)
        self._pipeline = PredictionPipeline(self._model, self._config)

    @classmethod
    def from_artifacts(
        cls,
        artifact_store: ExperimentArtifactStore,
        references: ApprovedModelReferences,
        *,
        config: InferenceRuntimeConfig | None = None,
        loader: ApprovedProductionModelLoader | None = None,
    ) -> "InferenceEngine":
        """Construct an engine only after complete Phase 7 evidence verification."""

        return cls(
            artifact_store,
            references,
            config=config,
            loader=loader,
        )

    @property
    def model_id(self) -> str:
        """Return the immutable identifier of the loaded approved model."""

        return self._model.registration.model_id

    def predict(
        self,
        feature_vector: ValidatedRawFeatureVector,
        *,
        group_id: str | None = None,
    ) -> InferencePrediction:
        """Predict one synchronization group from one validated feature vector."""

        selected_group = group_id or self._single_group_id(feature_vector)
        return self._pipeline.predict(
            (
                InferenceRequest(
                    feature_vector=feature_vector,
                    group_id=selected_group,
                ),
            )
        )[0]

    def predict_batch(
        self,
        requests: Sequence[InferenceRequest],
    ) -> tuple[InferencePrediction, ...]:
        """Predict one ordered batch with a single vectorized model invocation."""

        return self._pipeline.predict(tuple(requests))

    @staticmethod
    def _single_group_id(
        feature_vector: ValidatedRawFeatureVector,
    ) -> str:
        if len(feature_vector.groups) != 1:
            raise InferenceInputError(
                "group_id is required when a feature vector contains multiple groups."
            )
        return next(iter(feature_vector.groups))


ProductionInferenceEngine = InferenceEngine
