"""Deterministic serialization, loading, and failure-path tests."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.models import (
    BenchmarkModelSerializer,
    DummyMeanRegressorAdapter,
    LinearRegressionAdapter,
    RandomForestRegressorAdapter,
    RidgeRegressionAdapter,
)
from app.models.exceptions import BenchmarkSerializationError
from tests.models.helpers import make_benchmark_dataset, make_execution_request


@pytest.mark.parametrize(
    "adapter",
    (
        DummyMeanRegressorAdapter(),
        LinearRegressionAdapter(),
        RidgeRegressionAdapter(alpha=0.5),
        RandomForestRegressorAdapter(n_estimators=4, max_depth=3),
    ),
)
def test_every_benchmark_artifact_round_trips_canonically(adapter) -> None:
    dataset = make_benchmark_dataset()
    request = make_execution_request(dataset, adapter)
    output = adapter.execute(request)
    checksum = hashlib.sha256(output.model_artifact).hexdigest()

    loaded = BenchmarkModelSerializer.loads(
        output.model_artifact,
        expected_sha256=checksum,
    )

    assert BenchmarkModelSerializer.dumps(loaded.artifact) == output.model_artifact


def test_loading_rejects_checksum_mismatch_and_noncanonical_json() -> None:
    dataset = make_benchmark_dataset()
    adapter = DummyMeanRegressorAdapter()
    output = adapter.execute(make_execution_request(dataset, adapter))

    with pytest.raises(BenchmarkSerializationError):
        BenchmarkModelSerializer.loads(
            output.model_artifact,
            expected_sha256="0" * 64,
        )

    payload = json.loads(output.model_artifact)
    noncanonical = json.dumps(payload, indent=2).encode("utf-8")
    with pytest.raises(BenchmarkSerializationError):
        BenchmarkModelSerializer.loads(noncanonical)


def test_loading_rejects_tampered_predictive_payload() -> None:
    dataset = make_benchmark_dataset()
    adapter = DummyMeanRegressorAdapter()
    output = adapter.execute(make_execution_request(dataset, adapter))
    payload = json.loads(output.model_artifact)
    payload["constant_values"] = []
    tampered = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")

    with pytest.raises(BenchmarkSerializationError):
        BenchmarkModelSerializer.loads(tampered)
