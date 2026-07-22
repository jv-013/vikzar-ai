"""External, explainable release gates for evaluation reports."""

from __future__ import annotations

from .contracts import MetricResult, ReleaseGatePolicy, ReleaseGateResult


def evaluate_release_gates(
    metrics: tuple[MetricResult, ...],
    policy: ReleaseGatePolicy,
) -> tuple[ReleaseGateResult, ...]:
    """Evaluate policy gates without promoting, altering, or training a model."""

    results: list[ReleaseGateResult] = []
    for metric in metrics:
        target = metric.target_name
        results.append(
            _result(
                "minimum_sample_count",
                target,
                metric.sample_count >= policy.minimum_sample_count,
                metric.sample_count,
                policy.minimum_sample_count,
                "Sample count meets release minimum."
                if metric.sample_count >= policy.minimum_sample_count
                else "Sample count is below release minimum.",
            )
        )
        if policy.require_complete_predictions:
            results.append(
                _result(
                    "missing_prediction_detection",
                    target,
                    metric.missing_prediction_count == 0,
                    metric.missing_prediction_count,
                    0,
                    "All ground-truth rows have predictions."
                    if metric.missing_prediction_count == 0
                    else "One or more ground-truth rows are missing predictions.",
                )
            )
        if policy.minimum_r_squared is not None:
            passed = metric.r_squared is not None and metric.r_squared >= policy.minimum_r_squared
            results.append(
                _result(
                    "minimum_r_squared",
                    target,
                    passed,
                    metric.r_squared,
                    policy.minimum_r_squared,
                    "R-squared meets release minimum."
                    if passed
                    else "R-squared is unavailable or below release minimum.",
                )
            )
        if policy.maximum_rmse is not None:
            passed = metric.rmse is not None and metric.rmse <= policy.maximum_rmse
            results.append(
                _result(
                    "maximum_rmse",
                    target,
                    passed,
                    metric.rmse,
                    policy.maximum_rmse,
                    "RMSE is within release maximum."
                    if passed
                    else "RMSE is unavailable or exceeds release maximum.",
                )
            )
    return tuple(results)


def _result(
    gate_name: str,
    target_name: str,
    passed: bool,
    observed_value: float | int | None,
    threshold: float | int | None,
    message: str,
) -> ReleaseGateResult:
    return ReleaseGateResult(
        gate_name=gate_name,
        target_name=target_name,
        passed=passed,
        observed_value=observed_value,
        threshold=threshold,
        message=message,
    )
