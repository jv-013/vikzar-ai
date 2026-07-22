"""Unit and scientific regression tests for permanent Phase 6 models."""

from __future__ import annotations

import numpy as np
import pytest

from app.models import (
    BenchmarkModelSerializer,
    DummyMeanRegressorAdapter,
    LinearRegressionAdapter,
    RandomForestRegressorAdapter,
    RidgeRegressionAdapter,
)
from app.models.exceptions import BenchmarkConfigurationError
from tests.models.helpers import make_benchmark_dataset, make_execution_request


def _prediction_matrix(output, request) -> np.ndarray:
    values = {
        (row.example_id, row.target_name): row.value for row in output.prediction_rows
    }
    return np.asarray(
        [
            [
                values[(input_row.example_id, target_name)]
                for target_name in request.dataset.feature_schema.target_names
            ]
            for input_row in request.prediction_inputs
        ],
        dtype=np.float64,
    )


def _feature_matrix(request) -> np.ndarray:
    return np.asarray(
        [[item.value for item in row.features] for row in request.prediction_inputs],
        dtype=np.float64,
    )


def test_dummy_mean_is_the_exact_training_mean_reference() -> None:
    dataset = make_benchmark_dataset()
    adapter = DummyMeanRegressorAdapter()
    request = make_execution_request(dataset, adapter)

    output = adapter.execute(request)
    predictions = _prediction_matrix(output, request)
    expected = np.asarray(
        [
            [target.value for target in example.targets]
            for example in request.training_examples
        ],
        dtype=np.float64,
    ).mean(axis=0)

    assert np.allclose(predictions, expected)
    loaded = BenchmarkModelSerializer.loads(output.model_artifact)
    assert np.array_equal(loaded.predict(_feature_matrix(request)), predictions)


def test_linear_regression_recovers_the_known_multi_output_relationship() -> None:
    dataset = make_benchmark_dataset()
    adapter = LinearRegressionAdapter()
    request = make_execution_request(dataset, adapter)

    output = adapter.execute(request)
    loaded = BenchmarkModelSerializer.loads(output.model_artifact)

    assert np.allclose(
        loaded.artifact.coefficients,
        ((0.5, 2.0), (-0.1, 0.25)),
        atol=1e-10,
    )
    assert np.allclose(loaded.artifact.intercepts, (1.0, -2.0), atol=1e-10)
    expected = np.asarray(
        [
            [
                1.0 + 2.0 * row.features[1].value + 0.5 * row.features[0].value,
                -2.0 + 0.25 * row.features[1].value - 0.1 * row.features[0].value,
            ]
            for row in request.prediction_inputs
        ]
    )
    assert np.allclose(_prediction_matrix(output, request), expected, atol=1e-9)


def test_ridge_regression_is_deterministic_and_regularized() -> None:
    dataset = make_benchmark_dataset()
    adapter = RidgeRegressionAdapter(alpha=2.0)
    request = make_execution_request(dataset, adapter)

    first = adapter.execute(request)
    second = adapter.execute(request)
    loaded = BenchmarkModelSerializer.loads(first.model_artifact)

    assert first == second
    assert BenchmarkModelSerializer.dumps(loaded.artifact) == first.model_artifact
    assert np.isfinite(_prediction_matrix(first, request)).all()
    with pytest.raises(BenchmarkConfigurationError):
        RidgeRegressionAdapter(alpha=0.0)


def test_random_forest_training_prediction_and_artifact_are_deterministic() -> None:
    dataset = make_benchmark_dataset()
    adapter = RandomForestRegressorAdapter(
        n_estimators=8,
        max_depth=5,
        max_features_fraction=0.5,
        random_seed=73,
    )
    request = make_execution_request(dataset, adapter)

    first = adapter.execute(request)
    second = adapter.execute(request)
    loaded = BenchmarkModelSerializer.loads(first.model_artifact)

    assert first == second
    assert len(loaded.artifact.trees) == 8
    assert np.array_equal(
        loaded.predict(_feature_matrix(request)),
        _prediction_matrix(first, request),
    )
    with pytest.raises(BenchmarkConfigurationError):
        RandomForestRegressorAdapter(n_estimators=0)
