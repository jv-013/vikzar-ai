"""Pure deterministic regression metrics for algorithm-independent evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricValues:
    """Calculated scalar metrics before conversion to public report contracts."""

    mae: float | None
    rmse: float | None
    r_squared: float | None
    pearson_correlation: float | None
    bias: float | None


def calculate_regression_metrics(actual: tuple[float, ...], predicted: tuple[float, ...]) -> MetricValues:
    """Calculate deterministic metrics without fitting, transforming, or imputing data."""

    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted values must have equal lengths.")
    if not actual:
        return MetricValues(None, None, None, None, None)
    errors = tuple(prediction - truth for truth, prediction in zip(actual, predicted))
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    bias = sum(errors) / len(errors)
    mean_actual = sum(actual) / len(actual)
    total_sum_squares = sum((value - mean_actual) ** 2 for value in actual)
    residual_sum_squares = sum(error * error for error in errors)
    r_squared = 1.0 - (residual_sum_squares / total_sum_squares) if total_sum_squares > 0 else None
    pearson = _pearson(actual, predicted)
    return MetricValues(mae, rmse, r_squared, pearson, bias)


def _pearson(actual: tuple[float, ...], predicted: tuple[float, ...]) -> float | None:
    """Return Pearson correlation only when both series have variance."""

    if len(actual) < 2:
        return None
    mean_actual = sum(actual) / len(actual)
    mean_predicted = sum(predicted) / len(predicted)
    numerator = sum(
        (truth - mean_actual) * (prediction - mean_predicted)
        for truth, prediction in zip(actual, predicted)
    )
    actual_square_sum = sum((truth - mean_actual) ** 2 for truth in actual)
    predicted_square_sum = sum((prediction - mean_predicted) ** 2 for prediction in predicted)
    denominator = math.sqrt(actual_square_sum * predicted_square_sum)
    if denominator == 0:
        return None
    # Floating-point arithmetic can exceed the mathematical bounds by a few
    # ulps for perfectly correlated values.
    return max(-1.0, min(1.0, numerator / denominator))
