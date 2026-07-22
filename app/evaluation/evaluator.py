"""Algorithm-independent deterministic evaluation of immutable prediction sets."""

from __future__ import annotations

import hashlib
import json

from app.config import evaluation_config

from .calibration import calculate_calibration
from .contracts import (
    CalibrationResult,
    EvaluationProvenance,
    EvaluationReport,
    EvaluationSlice,
    GroundTruthRow,
    MetricResult,
    PredictionRow,
    PredictionSet,
    ReleaseGatePolicy,
)
from .gates import evaluate_release_gates
from .metrics import calculate_regression_metrics
from .slicing import slice_ground_truth_rows


class EvaluationFramework:
    """Measure a submitted model prediction set without model-specific behavior."""

    def __init__(self, confidence_absolute_error_tolerance: float | None = None) -> None:
        tolerance = (
            evaluation_config.DEFAULT_CONFIDENCE_ABSOLUTE_ERROR_TOLERANCE
            if confidence_absolute_error_tolerance is None
            else confidence_absolute_error_tolerance
        )
        if tolerance < 0:
            raise ValueError("Confidence absolute-error tolerance must be non-negative.")
        self._confidence_absolute_error_tolerance = tolerance

    def evaluate(
        self,
        prediction_set: PredictionSet,
        gate_policy: ReleaseGatePolicy | None = None,
    ) -> EvaluationReport:
        """Produce a deterministic immutable report from already-produced values."""

        policy = gate_policy or ReleaseGatePolicy()
        predictions = {
            (row.example_id, row.target_name): row for row in prediction_set.prediction_rows
        }
        overall_metrics = tuple(
            self._metric_for_target(
                target_name=target_name,
                truth_rows=prediction_set.ground_truth_rows,
                predictions=predictions,
                evaluation_slice=None,
            )
            for target_name in prediction_set.provenance.target_names
        )
        sliced_metrics = tuple(
            metric
            for evaluation_slice, rows in slice_ground_truth_rows(prediction_set.ground_truth_rows)
            for target_name in prediction_set.provenance.target_names
            if any(row.target_name == target_name for row in rows)
            for metric in (
                self._metric_for_target(
                    target_name=target_name,
                    truth_rows=rows,
                    predictions=predictions,
                    evaluation_slice=evaluation_slice,
                ),
            )
        )
        calibration = tuple(
            self._calibration_for_target(
                target_name=target_name,
                truth_rows=prediction_set.ground_truth_rows,
                predictions=predictions,
                evaluation_slice=None,
            )
            for target_name in prediction_set.provenance.target_names
        )
        gate_results = evaluate_release_gates(overall_metrics, policy)
        warnings = self._warnings(overall_metrics)
        failed_checks = tuple(result.message for result in gate_results if not result.passed)
        provenance = EvaluationProvenance(
            evaluation_schema_version=evaluation_config.EVALUATION_SCHEMA_VERSION,
            model_id=prediction_set.model_id,
            model_version=prediction_set.model_version,
            dataset_id=prediction_set.dataset_id,
            dataset_schema_version=prediction_set.provenance.dataset_schema_version,
            dataset_manifest_sha256=prediction_set.provenance.dataset_manifest_sha256,
            split_id=prediction_set.split_id,
            feature_schema_names=prediction_set.provenance.feature_schema_names,
            target_names=prediction_set.provenance.target_names,
        )
        provisional = EvaluationReport(
            report_id="pending",
            schema_version=evaluation_config.EVALUATION_SCHEMA_VERSION,
            evaluated_at=prediction_set.provenance.dataset_created_at,
            overall_metrics=overall_metrics,
            sliced_metrics=sliced_metrics,
            calibration=calibration,
            warnings=warnings,
            failed_checks=failed_checks,
            gate_results=gate_results,
            release_approved=not failed_checks,
            gate_policy=policy,
            provenance=provenance,
            report_checksum="0" * 64,
        )
        digest = self._sha256(
            provisional.model_dump(mode="json", exclude={"report_id", "report_checksum"})
        )
        return provisional.model_copy(
            update={"report_id": f"evaluation-{digest[:24]}", "report_checksum": digest}
        )

    def _metric_for_target(
        self,
        *,
        target_name: str,
        truth_rows: tuple[GroundTruthRow, ...],
        predictions: dict[tuple[str, str], PredictionRow],
        evaluation_slice: EvaluationSlice | None,
    ) -> MetricResult:
        rows = tuple(row for row in truth_rows if row.target_name == target_name)
        matched = tuple(
            (row, predictions[(row.example_id, row.target_name)])
            for row in rows
            if (row.example_id, row.target_name) in predictions
        )
        values = calculate_regression_metrics(
            tuple(row.value for row, _ in matched),
            tuple(prediction.value for _, prediction in matched),
        )
        return MetricResult(
            target_name=target_name,
            slice=evaluation_slice,
            mae=values.mae,
            rmse=values.rmse,
            r_squared=values.r_squared,
            pearson_correlation=values.pearson_correlation,
            bias=values.bias,
            coverage=len(matched) / len(rows) if rows else 0.0,
            sample_count=len(matched),
            missing_prediction_count=len(rows) - len(matched),
        )

    def _calibration_for_target(
        self,
        *,
        target_name: str,
        truth_rows: tuple[GroundTruthRow, ...],
        predictions: dict[tuple[str, str], PredictionRow],
        evaluation_slice: EvaluationSlice | None,
    ) -> CalibrationResult:
        rows = tuple(row for row in truth_rows if row.target_name == target_name)
        matched = tuple(
            (row, predictions[(row.example_id, row.target_name)])
            for row in rows
            if (row.example_id, row.target_name) in predictions
        )
        return calculate_calibration(
            target_name=target_name,
            evaluation_slice=evaluation_slice,
            actual=tuple(row.value for row, _ in matched),
            predicted=tuple(prediction.value for _, prediction in matched),
            confidence=tuple(prediction.confidence for _, prediction in matched),
            absolute_error_tolerance=self._confidence_absolute_error_tolerance,
        )

    @staticmethod
    def _warnings(metrics: tuple[MetricResult, ...]) -> tuple[str, ...]:
        warnings: list[str] = []
        for metric in metrics:
            if metric.sample_count == 0:
                warnings.append(f"{metric.target_name}: no matched predictions are available.")
            elif metric.r_squared is None:
                warnings.append(f"{metric.target_name}: R-squared is undefined for constant ground truth.")
            if metric.missing_prediction_count:
                warnings.append(
                    f"{metric.target_name}: {metric.missing_prediction_count} ground-truth rows lack predictions."
                )
        return tuple(warnings)

    @staticmethod
    def _sha256(payload: object) -> str:
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
