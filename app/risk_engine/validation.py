"""Validation of Phase 8 evidence and metadata before risk computation."""

from __future__ import annotations

from dataclasses import dataclass

from app.inference.contracts import InferencePrediction

from .configuration import RiskEngineConfig
from .contracts import RiskAssessmentRequest
from .exceptions import RiskInputError


@dataclass(frozen=True)
class ValidatedRiskContext:
    """Canonical prediction order and the latest comparable bilateral cohort."""

    request: RiskAssessmentRequest
    predictions: tuple[InferencePrediction, ...]
    latest_by_group: dict[str, InferencePrediction]
    values_by_prediction: dict[str, dict[str, float]]
    baseline_values: dict[tuple[str, str], float]
    history_windows: int


class RiskInputValidator:
    """Fail closed unless all Phase 8 evidence is comparable and traceable."""

    def validate(
        self,
        request: RiskAssessmentRequest,
        config: RiskEngineConfig,
    ) -> ValidatedRiskContext:
        predictions = tuple(sorted(request.predictions, key=self._sort_key))
        if len({item.prediction_id for item in predictions}) != len(predictions):
            raise RiskInputError("Risk input contains duplicate Phase 8 predictions.")
        if request.baseline.player_id != request.player.player_id:
            raise RiskInputError("Player baseline does not belong to the requested player.")

        first = predictions[0].metadata
        expected_lineage = (
            first.model_id,
            first.model_version,
            first.model_checksum.lower(),
            first.inference_configuration_hash.lower(),
            first.target_schema,
        )
        values_by_prediction: dict[str, dict[str, float]] = {}
        required_targets = set(config.asymmetry_target_names) | set(
            config.fatigue_target_names
        ) | {
            config.quadriceps_target_name,
            config.hamstring_target_name,
        }
        allowed_groups = {config.left_group_id, config.right_group_id}
        cohorts: dict[
            tuple[str, object, float, float],
            dict[str, InferencePrediction],
        ] = {}
        for prediction in predictions:
            metadata = prediction.metadata
            expected_checksum = InferencePrediction.calculate_checksum(
                prediction.predictions,
                metadata,
            )
            if (
                prediction.checksum.lower() != expected_checksum
                or prediction.prediction_id
                != f"prediction-{expected_checksum[:24]}"
            ):
                raise RiskInputError("Phase 8 prediction integrity verification failed.")
            if metadata.source_timestamp.utcoffset() is None:
                raise RiskInputError("Phase 8 source timestamps must include a timezone.")
            if metadata.player_id != request.player.player_id:
                raise RiskInputError("Prediction player identity is inconsistent.")
            if metadata.session_id != request.session.session_id:
                raise RiskInputError("Prediction session identity is inconsistent.")
            if metadata.group_id not in allowed_groups:
                raise RiskInputError("Prediction group is outside the configured limb pair.")
            lineage = (
                metadata.model_id,
                metadata.model_version,
                metadata.model_checksum.lower(),
                metadata.inference_configuration_hash.lower(),
                metadata.target_schema,
            )
            if lineage != expected_lineage:
                raise RiskInputError(
                    "All risk inputs must share one model, schema, and inference configuration."
                )
            values = {
                value.target_name: value.value for value in prediction.predictions
            }
            if not required_targets.issubset(values):
                raise RiskInputError(
                    "Phase 8 predictions do not contain every configured risk target."
                )
            if any(values[name] < 0 for name in required_targets):
                raise RiskInputError(
                    "Configured muscle-activity predictions must be non-negative."
                )
            values_by_prediction[prediction.prediction_id] = values
            cohort_key = (
                metadata.source_feature_vector_id,
                metadata.source_timestamp,
                metadata.window_start,
                metadata.window_end,
            )
            cohort = cohorts.setdefault(cohort_key, {})
            if metadata.group_id in cohort:
                raise RiskInputError(
                    "A Phase 8 source window has duplicate predictions for one group."
                )
            cohort[metadata.group_id] = prediction

        if any(set(cohort) != allowed_groups for cohort in cohorts.values()):
            raise RiskInputError(
                "Every risk-history window must contain the complete configured "
                "bilateral Phase 8 prediction pair."
            )
        complete = tuple(cohorts.items())
        _, latest = max(
            complete,
            key=lambda item: (
                item[0][1],
                item[0][3],
                item[0][0],
            ),
        )

        baseline_values = {
            (value.group_id, value.target_name): value.value
            for value in request.baseline.target_values
        }
        required_baselines = {
            (group_id, target_name)
            for group_id in allowed_groups
            for target_name in config.fatigue_target_names
        }
        if not required_baselines.issubset(baseline_values):
            raise RiskInputError(
                "Player baseline is missing a configured group/target reference."
            )
        return ValidatedRiskContext(
            request=request,
            predictions=predictions,
            latest_by_group=dict(latest),
            values_by_prediction=values_by_prediction,
            baseline_values=baseline_values,
            history_windows=len(cohorts),
        )

    @staticmethod
    def _sort_key(prediction: InferencePrediction) -> tuple[object, float, str, str]:
        metadata = prediction.metadata
        return (
            metadata.source_timestamp,
            metadata.window_end,
            metadata.group_id,
            prediction.prediction_id,
        )
