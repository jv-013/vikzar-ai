"""Integration, recovery, compatibility, and concurrency tests for Phase 5."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Lock

import pytest

from app.evaluation import ReleaseGatePolicy
from app.experiments.artifact_store import ExperimentArtifactStore
from app.experiments.contracts import ExperimentLifecycleState
from app.experiments.exceptions import (
    DuplicateExperimentError,
    ExperimentCompatibilityError,
    ExperimentLockError,
)
from app.experiments.registry import ExperimentRegistry
from app.experiments.runner import ExperimentRunner
from tests.experiments.helpers import (
    DeterministicMockAdapter,
    InterruptingAdapter,
    make_experiment_dataset,
    make_spec,
)


class StepClock:
    """Thread-safe deterministic execution clock."""

    def __init__(self) -> None:
        self._value = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
        self._lock = Lock()

    def __call__(self) -> datetime:
        with self._lock:
            current = self._value
            self._value += timedelta(seconds=1)
            return current


def _runner(root, clock: StepClock | None = None) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentArtifactStore(root),
        clock=clock or StepClock(),
        dependency_names=("pydantic",),
    )


def test_end_to_end_experiment_preserves_lineage_and_held_out_targets(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    adapter = DeterministicMockAdapter(dataset)
    runner = _runner(tmp_path)

    result = runner.run(
        spec=spec,
        dataset=dataset,
        adapter=adapter,
        gate_policy=ReleaseGatePolicy(maximum_rmse=0.0, minimum_sample_count=1),
    )

    assert result.promotion_recommendation.eligible is True
    assert result.provenance.configuration_hash == spec.configuration_hash
    assert result.provenance.dataset_checksum == spec.dataset_checksum
    assert result.evaluation_report.release_approved is True
    assert adapter.observed_request is not None
    assert all(
        not hasattr(input_row, "targets")
        for input_row in adapter.observed_request.prediction_inputs
    )
    assert all(
        example.split.value == "train"
        for example in adapter.observed_request.training_examples
    )
    store = ExperimentArtifactStore(tmp_path)
    for reference in result.artifact_references:
        store.verify(reference)
    history = ExperimentRegistry(store).history(spec.experiment_id)
    assert tuple(event.state for event in history) == (
        ExperimentLifecycleState.RUNNING,
        ExperimentLifecycleState.COMPLETED,
    )
    assert not (tmp_path / "registry" / spec.experiment_id / "running.lock").exists()


def test_identical_configuration_is_warned_without_reusing_history(tmp_path) -> None:
    dataset = make_experiment_dataset()
    first_spec = make_spec(dataset, experiment_id="exp-first")
    second_spec = make_spec(dataset, experiment_id="exp-second")
    runner = _runner(tmp_path)

    first = runner.run(
        spec=first_spec,
        dataset=dataset,
        adapter=DeterministicMockAdapter(dataset),
    )
    second = runner.run(
        spec=second_spec,
        dataset=dataset,
        adapter=DeterministicMockAdapter(dataset),
    )

    assert first.spec.configuration_hash == second.spec.configuration_hash
    assert first.reproducibility_checksum == second.reproducibility_checksum
    assert first.provenance.model_artifact_checksum == second.provenance.model_artifact_checksum
    assert first.provenance.evaluation_report_checksum == second.provenance.evaluation_report_checksum
    assert second.warnings == (
        "Identical configuration already registered for experiment IDs: exp-first",
    )
    assert ExperimentRegistry(ExperimentArtifactStore(tmp_path)).experiments_for_configuration(
        first.spec.configuration_hash
    ) == ("exp-first", "exp-second")


def test_completed_experiment_id_is_never_reused(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    runner = _runner(tmp_path)
    runner.run(spec=spec, dataset=dataset, adapter=DeterministicMockAdapter(dataset))

    with pytest.raises(DuplicateExperimentError):
        runner.run(
            spec=spec,
            dataset=dataset,
            adapter=DeterministicMockAdapter(dataset),
        )
    with pytest.raises(DuplicateExperimentError):
        runner.run(
            spec=spec,
            dataset=dataset,
            adapter=DeterministicMockAdapter(dataset),
            recover=True,
        )


def test_interrupted_experiment_recovers_as_a_new_append_only_attempt(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    runner = _runner(tmp_path)

    with pytest.raises(KeyboardInterrupt):
        runner.run(spec=spec, dataset=dataset, adapter=InterruptingAdapter())

    recovered = runner.run(
        spec=spec,
        dataset=dataset,
        adapter=DeterministicMockAdapter(dataset),
        recover=True,
    )
    history = ExperimentRegistry(ExperimentArtifactStore(tmp_path)).history(
        spec.experiment_id
    )

    assert recovered.execution_summary.attempt == 2
    assert tuple(event.state for event in history) == (
        ExperimentLifecycleState.RUNNING,
        ExperimentLifecycleState.INTERRUPTED,
        ExperimentLifecycleState.RUNNING,
        ExperimentLifecycleState.COMPLETED,
    )
    assert history[2].recovered_from_run_id == history[0].run_id


def test_incompatible_adapter_is_failed_and_can_be_explicitly_recovered(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    runner = _runner(tmp_path)

    class WrongAlgorithmAdapter(DeterministicMockAdapter):
        algorithm_identifier = "wrong-algorithm"

    with pytest.raises(ExperimentCompatibilityError):
        runner.run(
            spec=spec,
            dataset=dataset,
            adapter=WrongAlgorithmAdapter(dataset),
        )

    result = runner.run(
        spec=spec,
        dataset=dataset,
        adapter=DeterministicMockAdapter(dataset),
        recover=True,
    )
    assert result.execution_summary.attempt == 2


def test_adapter_output_schema_mismatch_is_rejected_and_audited(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    runner = _runner(tmp_path)

    class WrongSchemaAdapter(DeterministicMockAdapter):
        def execute(self, request):
            output = super().execute(request)
            return output.model_copy(update={"feature_schema": ("unexpected-feature",)})

    with pytest.raises(ExperimentCompatibilityError):
        runner.run(
            spec=spec,
            dataset=dataset,
            adapter=WrongSchemaAdapter(dataset),
        )

    history = ExperimentRegistry(ExperimentArtifactStore(tmp_path)).history(
        spec.experiment_id
    )
    assert tuple(event.state for event in history) == (
        ExperimentLifecycleState.RUNNING,
        ExperimentLifecycleState.FAILED,
    )


def test_concurrent_same_id_execution_fails_immediately_under_lock(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    started = Event()
    release = Event()
    blocking = DeterministicMockAdapter(
        dataset,
        started=started,
        release=release,
    )
    first_runner = _runner(tmp_path, StepClock())
    second_runner = _runner(tmp_path, StepClock())

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            first_runner.run,
            spec=spec,
            dataset=dataset,
            adapter=blocking,
        )
        assert started.wait(timeout=10)
        with pytest.raises(ExperimentLockError):
            second_runner.run(
                spec=spec,
                dataset=dataset,
                adapter=DeterministicMockAdapter(dataset),
            )
        release.set()
        assert future.result().spec.experiment_id == spec.experiment_id
