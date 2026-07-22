"""Phase 3–7 integration helpers using permanent Phase 6 benchmarks."""

from __future__ import annotations

from datetime import datetime, timezone

from app.benchmarking import BenchmarkTrainer
from app.evaluation import ReleaseGatePolicy
from app.experiments.artifact_store import ExperimentArtifactStore
from app.experiments.runner import ExperimentRunner
from app.models import (
    DummyMeanRegressorAdapter,
    LinearRegressionAdapter,
    RandomForestRegressorAdapter,
    RidgeRegressionAdapter,
)
from app.models.production import (
    ProductionModelRegistry,
    ProductionTrainer,
)
from tests.models.helpers import make_benchmark_dataset


def make_phase_seven_context(root):
    """Return one normal Phase 3 dataset, benchmark evidence, and production trainer."""

    dataset = make_benchmark_dataset()
    store = ExperimentArtifactStore(root)
    policy = ReleaseGatePolicy(minimum_sample_count=1)
    benchmark_trainer = BenchmarkTrainer(
        ExperimentRunner(store, dependency_names=("numpy", "pydantic")),
        clock=lambda: datetime(2026, 7, 19, 12, tzinfo=timezone.utc),
    )
    adapters = (
        ("p7-benchmark-dummy", DummyMeanRegressorAdapter()),
        ("p7-benchmark-linear", LinearRegressionAdapter()),
        ("p7-benchmark-ridge", RidgeRegressionAdapter(alpha=0.5)),
        (
            "p7-benchmark-forest",
            RandomForestRegressorAdapter(n_estimators=4, max_depth=3),
        ),
    )
    benchmarks = tuple(
        benchmark_trainer.run(
            experiment_id=experiment_id,
            dataset=dataset,
            adapter=adapter,
            created_by="phase-seven-tests",
            gate_policy=policy,
        )
        for experiment_id, adapter in adapters
    )
    trainer = ProductionTrainer(
        ExperimentRunner(store, dependency_names=("numpy", "pydantic")),
        ProductionModelRegistry(store),
        clock=lambda: datetime(2026, 7, 19, 13, tzinfo=timezone.utc),
    )
    return dataset, benchmarks, policy, trainer, store
