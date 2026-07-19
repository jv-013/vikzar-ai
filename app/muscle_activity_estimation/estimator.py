"""Orchestrate implementation-independent muscle activity estimation."""

from __future__ import annotations

import logging

from app.lookup_engine.entities import LookupResult
from app.muscle_activity_estimation.entities import (
    EstimationProvenance,
    FrozenMetricMap,
    MuscleActivityEstimate,
    MuscleEstimationOutput,
)
from app.muscle_activity_estimation.exceptions import (
    MuscleEstimationInputError,
    MuscleEstimationModelExecutionError,
    MuscleEstimationOutputError,
)
from app.muscle_activity_estimation.model import MuscleEstimationModel
from app.schemas.feature_vector import FeatureVector


logger = logging.getLogger("app.muscle_activity_estimation")


class MuscleActivityEstimator:
    """Create immutable muscle estimates through an injected model interface.

    Parameters:
        model: Implementation-independent muscle estimation dependency.
        estimator_version: Version of this orchestration behavior.

    Returns:
        An estimator that preserves source inputs and returns immutable output.

    Exceptions:
        ValueError: Raised when estimator_version is blank.
    """

    def __init__(
        self,
        model: MuscleEstimationModel,
        estimator_version: str,
    ) -> None:
        if not estimator_version.strip():
            raise ValueError("estimator_version must be a non-empty string.")
        self._model = model
        self._estimator_version = estimator_version

    def estimate(
        self,
        feature_vector: FeatureVector,
        lookup_result: LookupResult,
    ) -> MuscleActivityEstimate:
        """Estimate muscle activity for one validated FeatureVector.

        Parameters:
            feature_vector: FeatureVector already accepted by validation.
            lookup_result: Immutable Lookup Engine output for the same vector.

        Returns:
            Immutable, model-produced muscle estimates with input provenance.

        Exceptions:
            MuscleEstimationInputError: Raised when input identifiers disagree.
            MuscleEstimationModelExecutionError: Raised when the injected model
                raises unexpectedly.
            MuscleEstimationOutputError: Raised when the model return type or
                public output contract is invalid.
        """

        feature_vector_id = feature_vector.metadata.feature_vector_id
        if lookup_result.feature_vector_id != feature_vector_id:
            self._log_input_failure(feature_vector_id, lookup_result.feature_vector_id)
            raise MuscleEstimationInputError(
                "FeatureVector and LookupResult must reference the same feature vector."
            )

        output = self._run_model(feature_vector, lookup_result)
        try:
            estimate = MuscleActivityEstimate(
                feature_vector_id=feature_vector_id,
                estimator_version=self._estimator_version,
                model_version=output.model_version,
                confidence=output.confidence,
                muscles=FrozenMetricMap(output.muscles),
                derived_metrics=FrozenMetricMap(output.derived_metrics),
                provenance=EstimationProvenance(
                    feature_vector_id=feature_vector_id,
                    lookup_result_feature_vector_id=lookup_result.feature_vector_id,
                    scientific_source_ids=tuple(
                        source.source_id for source in lookup_result.scientific_sources
                    ),
                ),
            )
        except (TypeError, ValueError) as exc:
            self._log_output_failure(feature_vector_id, exc)
            raise MuscleEstimationOutputError(
                "Muscle estimation model output does not satisfy the public contract."
            ) from exc

        self._log_success(estimate)
        return estimate

    def _run_model(
        self,
        feature_vector: FeatureVector,
        lookup_result: LookupResult,
    ) -> MuscleEstimationOutput:
        """Invoke the injected model and verify its declared return contract."""

        try:
            output = self._model.estimate(feature_vector, lookup_result)
        except Exception as exc:
            logger.exception(
                "Muscle estimation model execution failed.",
                extra={
                    "component": "muscle_activity_estimation",
                    "feature_vector_id": feature_vector.metadata.feature_vector_id,
                    "exception_type": exc.__class__.__name__,
                },
            )
            raise MuscleEstimationModelExecutionError(
                "Muscle estimation model execution failed."
            ) from exc

        if not isinstance(output, MuscleEstimationOutput):
            self._log_output_failure(
                feature_vector.metadata.feature_vector_id,
                TypeError("Unexpected model output type."),
            )
            raise MuscleEstimationOutputError(
                "Muscle estimation model must return MuscleEstimationOutput."
            )
        return output

    @staticmethod
    def _log_success(estimate: MuscleActivityEstimate) -> None:
        """Log successful estimation without recording metric values."""

        logger.info(
            "Muscle activity estimation completed.",
            extra={
                "component": "muscle_activity_estimation",
                "feature_vector_id": estimate.feature_vector_id,
                "estimator_version": estimate.estimator_version,
                "model_version": estimate.model_version,
                "muscle_metric_count": len(estimate.muscles),
                "derived_metric_count": len(estimate.derived_metrics),
                "scientific_source_count": len(estimate.provenance.scientific_source_ids),
            },
        )

    @staticmethod
    def _log_input_failure(
        feature_vector_id: str,
        lookup_result_feature_vector_id: str,
    ) -> None:
        """Log identifier mismatch without disclosing feature values."""

        logger.warning(
            "Muscle activity estimation input identifiers do not match.",
            extra={
                "component": "muscle_activity_estimation",
                "feature_vector_id": feature_vector_id,
                "lookup_result_feature_vector_id": lookup_result_feature_vector_id,
            },
        )

    @staticmethod
    def _log_output_failure(feature_vector_id: str, exc: Exception) -> None:
        """Log malformed model output using structured failure metadata."""

        logger.warning(
            "Muscle estimation model returned invalid output.",
            extra={
                "component": "muscle_activity_estimation",
                "feature_vector_id": feature_vector_id,
                "exception_type": exc.__class__.__name__,
            },
        )
