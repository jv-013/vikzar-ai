"""Unit, deterministic training, regression, and loading tests."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from pydantic import ValidationError

from app.models.production import (
    ProductionModelConfig,
    ProductionModelFactory,
    ProductionModelSerializer,
)
from app.models.production.exceptions import ProductionSerializationError
from tests.models.helpers import make_benchmark_dataset, make_execution_request


def test_production_configuration_is_immutable_and_factory_is_deterministic() -> None:
    config = ProductionModelConfig(hidden_layer_sizes=(6, 4), epochs=40)
    first = ProductionModelFactory.create(config)
    second = ProductionModelFactory.create(config)

    assert first.hyperparameters == second.hyperparameters
    assert first.random_seed == second.random_seed
    with pytest.raises(ValidationError):
        config.epochs = 2  # type: ignore[misc]


def test_training_serialization_loading_and_predictions_are_deterministic() -> None:
    dataset = make_benchmark_dataset()
    adapter = ProductionModelFactory.create(
        ProductionModelConfig(
            hidden_layer_sizes=(8,),
            learning_rate=0.02,
            epochs=80,
            random_seed=211,
        )
    )
    request = make_execution_request(dataset, adapter)

    first = adapter.execute(request)
    second = adapter.execute(request)
    checksum = hashlib.sha256(first.model_artifact).hexdigest()
    loaded = ProductionModelSerializer.loads(
        first.model_artifact,
        expected_sha256=checksum,
    )
    features = np.asarray(
        [[item.value for item in row.features] for row in request.prediction_inputs]
    )

    assert first == second
    assert ProductionModelSerializer.dumps(loaded.artifact) == first.model_artifact
    assert np.isfinite(loaded.predict(features)).all()
    assert loaded.artifact.training_summary.selected_epoch <= 80
    assert loaded.artifact.training_summary.validation_example_count > 0


def test_loading_rejects_checksum_failure_and_tampering() -> None:
    dataset = make_benchmark_dataset()
    adapter = ProductionModelFactory.create(
        ProductionModelConfig(hidden_layer_sizes=(4,), epochs=10)
    )
    output = adapter.execute(make_execution_request(dataset, adapter))

    with pytest.raises(ProductionSerializationError):
        ProductionModelSerializer.loads(
            output.model_artifact,
            expected_sha256="0" * 64,
        )
    tampered = output.model_artifact.replace(
        b'"schema_version":"1.0.0"',
        b'"schema_version":"9.0.0"',
        1,
    )
    with pytest.raises(ProductionSerializationError):
        ProductionModelSerializer.loads(tampered)
