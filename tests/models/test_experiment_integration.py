"""Phase 3–6 integration, registration, evaluation, and reproducibility tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.benchmarking import BenchmarkTrainer
from app.evaluation import ReleaseGatePolicy
from app.experiments.artifact_store import ExperimentArtifactStore
from app.experiments.contracts import ExperimentLifecycleState
from app.experiments.registry import ExperimentRegistry
from app.experiments.runner import ExperimentRunner
from app.models import (
    DummyMeanRegressorAdapter,
    LinearRegressionAdapter,
    RandomForestRegressorAdapter,
    RidgeRegressionAdapter,
)
from tests.models.helpers import make_benchmark_dataset


def _trainer(root) -> BenchmarkTrainer:
    runner = ExperimentRunner(
        ExperimentArtifactStore(root),
        dependency_names=("numpy", "pydantic"),
    )
    return BenchmarkTrainer(
        runner,
        clock=lambda: datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize(
    ("experiment_id", "adapter"),
    (
        ("benchmark-dummy", DummyMeanRegressorAdapter()),
        ("benchmark-linear", LinearRegressionAdapter()),
        ("benchmark-ridge", RidgeRegressionAdapter(alpha=0.5)),
        (
            "benchmark-random-forest",
            RandomForestRegressorAdapter(n_estimators=6, max_depth=4),
        ),
    ),
)
def test_every_benchmark_automatically_registers_and_uses_phase_four(
    tmp_path,
    experiment_id,
    adapter,
) -> None:
    dataset = make_benchmark_dataset()

    result = _trainer(tmp_path).run(
        experiment_id=experiment_id,
        dataset=dataset,
        adapter=adapter,
        created_by="phase-six-integration",
        gate_policy=ReleaseGatePolicy(minimum_sample_count=1),
    )

    assert result.spec.algorithm_identifier == adapter.algorithm_identifier
    assert result.spec.hyperparameters == adapter.hyperparameters
    assert result.spec.random_seed == adapter.random_seed
    assert result.provenance.dataset_checksum == result.spec.dataset_checksum
    assert result.evaluation_report.provenance.dataset_id == dataset.dataset.dataset_id
    assert result.evaluation_report.schema_version == "1.0.0"
    history = ExperimentRegistry(ExperimentArtifactStore(tmp_path)).history(
        experiment_id
    )
    assert tuple(event.state for event in history) == (
        ExperimentLifecycleState.RUNNING,
        ExperimentLifecycleState.COMPLETED,
    )
    for reference in history[-1].artifact_references:
        ExperimentArtifactStore(tmp_path).verify(reference)


def test_identical_benchmark_runs_reproduce_checksums_under_unique_ids(tmp_path) -> None:
    dataset = make_benchmark_dataset()
    adapter = RidgeRegressionAdapter(alpha=1.25, random_seed=89)
    trainer = _trainer(tmp_path)

    first = trainer.run(
        experiment_id="benchmark-reproduction-a",
        dataset=dataset,
        adapter=adapter,
        created_by="phase-six-reproduction",
    )
    second = trainer.run(
        experiment_id="benchmark-reproduction-b",
        dataset=dataset,
        adapter=adapter,
        created_by="phase-six-reproduction",
    )

    assert first.spec.configuration_hash == second.spec.configuration_hash
    assert first.provenance.model_artifact_checksum == second.provenance.model_artifact_checksum
    assert first.provenance.evaluation_report_checksum == (
        second.provenance.evaluation_report_checksum
    )
    assert first.reproducibility_checksum == second.reproducibility_checksum
    assert second.warnings == (
        "Identical configuration already registered for experiment IDs: "
        "benchmark-reproduction-a",
    )


def test_linear_benchmark_release_gates_are_applied_only_by_phase_four(tmp_path) -> None:
    dataset = make_benchmark_dataset()

    result = _trainer(tmp_path).run(
        experiment_id="benchmark-linear-release-gates",
        dataset=dataset,
        adapter=LinearRegressionAdapter(),
        created_by="phase-six-evaluation",
        gate_policy=ReleaseGatePolicy(
            minimum_r_squared=0.999,
            maximum_rmse=1e-8,
            minimum_sample_count=1,
        ),
    )

    assert result.evaluation_report.release_approved is True
    assert result.promotion_recommendation.eligible is True
    assert all(gate.passed for gate in result.evaluation_report.gate_results)
