"""Algorithm-independent metric, slicing, gate, and reproducibility tests."""

from __future__ import annotations

import pytest

from app.evaluation import EvaluationFramework, ReleaseGatePolicy

from .helpers import make_dataset_result, make_prediction_set


def test_perfect_predictions_measure_zero_error_and_full_coverage() -> None:
    """Perfect submitted predictions evaluate without any model-specific path."""

    report = EvaluationFramework().evaluate(make_prediction_set(make_dataset_result()))

    assert report.release_approved
    assert all(metric.mae == 0.0 and metric.rmse == 0.0 for metric in report.overall_metrics)
    assert all(metric.coverage == 1.0 and metric.r_squared == 1.0 for metric in report.overall_metrics)


def test_noisy_predictions_measure_expected_bias_and_gate_failure() -> None:
    """Release policy—not a model—determines whether noisy output can pass."""

    prediction_set = make_prediction_set(make_dataset_result(), offset=0.2)
    report = EvaluationFramework().evaluate(
        prediction_set,
        ReleaseGatePolicy(maximum_rmse=0.1, minimum_sample_count=3),
    )

    assert not report.release_approved
    assert all(metric.mae == pytest.approx(0.2) and metric.bias == pytest.approx(0.2) for metric in report.overall_metrics)
    assert any(result.gate_name == "maximum_rmse" and not result.passed for result in report.gate_results)


def test_missing_prediction_reduces_coverage_and_fails_release_gate() -> None:
    """Evaluation records missing predictions rather than filling them."""

    report = EvaluationFramework().evaluate(
        make_prediction_set(make_dataset_result(), omit_first_prediction=True)
    )

    assert not report.release_approved
    assert sum(metric.missing_prediction_count for metric in report.overall_metrics) == 1
    assert any("lack predictions" in warning for warning in report.warnings)


def test_empty_submission_returns_failed_evidence_not_a_crash() -> None:
    """An empty evaluated split is explicit and cannot satisfy release gates."""

    report = EvaluationFramework().evaluate(make_prediction_set(make_dataset_result(), empty=True))

    assert not report.release_approved
    assert all(metric.sample_count == 0 for metric in report.overall_metrics)
    assert all("no matched predictions" in warning for warning in report.warnings)


def test_reports_player_and_dataset_split_subgroups() -> None:
    """Sliced metrics use Phase 3 provenance rather than model-specific metadata."""

    report = EvaluationFramework().evaluate(make_prediction_set(make_dataset_result()))

    dimensions = {metric.slice.dimension.value for metric in report.sliced_metrics if metric.slice is not None}
    assert {"player", "session", "dataset_split"}.issubset(dimensions)


def test_reports_position_and_drill_subgroups_when_submitted() -> None:
    """Optional context uses the same immutable prediction-set path."""

    prediction_set = make_prediction_set(make_dataset_result())
    rows = tuple(
        row.model_copy(update={"position": "midfielder", "drill_id": "planned_cut"})
        for row in prediction_set.ground_truth_rows
    )
    report = EvaluationFramework().evaluate(prediction_set.model_copy(update={"ground_truth_rows": rows}))

    dimensions = {metric.slice.dimension.value for metric in report.sliced_metrics if metric.slice is not None}
    assert {"position", "drill"}.issubset(dimensions)


def test_confidence_calibration_is_measured_without_changing_predictions() -> None:
    """Confidence is optional evidence and has a deterministic calibration result."""

    report = EvaluationFramework().evaluate(make_prediction_set(make_dataset_result()))

    assert all(result.available and result.empirical_agreement == 1.0 for result in report.calibration)


def test_same_submitted_evidence_produces_an_identical_report() -> None:
    """Report identity, timestamp, metrics, gates, and checksum are deterministic."""

    prediction_set = make_prediction_set(make_dataset_result())
    evaluator = EvaluationFramework()

    assert evaluator.evaluate(prediction_set).model_dump(mode="json") == evaluator.evaluate(
        prediction_set
    ).model_dump(mode="json")
