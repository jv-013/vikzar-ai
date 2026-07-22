"""Deterministic comparison tests using completed experiment evidence."""

from __future__ import annotations

from app.evaluation import ReleaseGatePolicy
from app.experiments.artifact_store import ExperimentArtifactStore
from app.experiments.comparison import ExperimentComparator
from app.experiments.runner import ExperimentRunner
from tests.experiments.helpers import (
    DeterministicMockAdapter,
    make_experiment_dataset,
    make_spec,
)


def test_comparison_is_deterministic_and_never_promotes_a_model(tmp_path) -> None:
    dataset = make_experiment_dataset()
    runner = ExperimentRunner(
        ExperimentArtifactStore(tmp_path),
        dependency_names=("pydantic",),
    )
    perfect = runner.run(
        spec=make_spec(dataset, experiment_id="exp-perfect"),
        dataset=dataset,
        adapter=DeterministicMockAdapter(dataset),
        gate_policy=ReleaseGatePolicy(maximum_rmse=1.0),
    )
    noisy = runner.run(
        spec=make_spec(dataset, experiment_id="exp-noisy"),
        dataset=dataset,
        adapter=DeterministicMockAdapter(dataset, offset=0.2),
        gate_policy=ReleaseGatePolicy(maximum_rmse=1.0),
    )

    comparison = ExperimentComparator().compare((noisy, perfect))
    repeated = ExperimentComparator().compare((perfect, noisy))

    assert comparison == repeated
    assert comparison.recommended_experiment_id == "exp-perfect"
    assert "manual promotion remains required" in comparison.rationale
    reference = ExperimentArtifactStore(tmp_path).write_json(
        relative_path=f"comparisons/{comparison.comparison_id}.json",
        artifact_type="experiment_comparison",
        payload=comparison,
    )
    ExperimentArtifactStore(tmp_path).verify(reference)
