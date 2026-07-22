"""Deterministic, model-independent comparison of completed experiment evidence."""

from __future__ import annotations

import hashlib
import json

from .contracts import ExperimentComparison, ExperimentResult


class ExperimentComparator:
    """Compare evaluation evidence without training, evaluating, or promoting models."""

    def compare(self, results: tuple[ExperimentResult, ...]) -> ExperimentComparison:
        """Return an immutable recommendation based only on approved report metrics."""

        ordered = tuple(sorted(results, key=lambda result: result.spec.experiment_id))
        if len(ordered) < 2:
            raise ValueError("At least two experiment results are required for comparison.")
        if len({result.spec.experiment_id for result in ordered}) != len(ordered):
            raise ValueError("Comparison requires unique experiment IDs.")
        eligible = tuple(
            result for result in ordered if result.promotion_recommendation.eligible
        )
        recommended = (
            min(eligible, key=self._mean_rmse).spec.experiment_id if eligible else None
        )
        rationale = (
            "Lowest mean overall RMSE among evaluation-approved candidates; manual promotion remains required."
            if recommended is not None
            else "No compared candidate passed its external evaluation release gates."
        )
        payload = {
            "experiment_ids": [result.spec.experiment_id for result in ordered],
            "recommended": recommended,
            "rationale": rationale,
            "checksums": [result.reproducibility_checksum for result in ordered],
        }
        checksum = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return ExperimentComparison(
            comparison_id=f"comparison-{checksum[:24]}",
            experiment_ids=tuple(result.spec.experiment_id for result in ordered),
            recommended_experiment_id=recommended,
            rationale=rationale,
            checksum=checksum,
        )

    @staticmethod
    def _mean_rmse(result: ExperimentResult) -> float:
        values = tuple(
            metric.rmse
            for metric in result.evaluation_report.overall_metrics
            if metric.rmse is not None
        )
        return sum(values) / len(values) if values else float("inf")
