"""Immutable artifact, checksum, registry, and locking tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.experiments.artifact_store import ExperimentArtifactStore
from app.experiments.configuration import EnvironmentCollector
from app.experiments.exceptions import (
    DuplicateExperimentError,
    ExperimentLockError,
    ExperimentStorageError,
)
from app.experiments.locking import ExperimentLockManager
from app.experiments.registry import ExperimentRegistry
from tests.experiments.helpers import make_experiment_dataset, make_spec


def test_binary_artifacts_are_immutable_and_checksum_verified(tmp_path) -> None:
    store = ExperimentArtifactStore(tmp_path)
    reference = store.write_bytes(
        relative_path="experiments/exp-1/model.bin",
        artifact_type="model",
        payload=b"deterministic-model",
    )

    assert store.write_bytes(
        relative_path="experiments/exp-1/model.bin",
        artifact_type="model",
        payload=b"deterministic-model",
    ) == reference
    store.verify(reference)
    with pytest.raises(ExperimentStorageError):
        store.write_bytes(
            relative_path="experiments/exp-1/model.bin",
            artifact_type="model",
            payload=b"different-model",
        )

    (tmp_path / reference.relative_path).write_bytes(b"tampered")
    with pytest.raises(ExperimentStorageError):
        store.verify(reference)


def test_artifact_paths_cannot_escape_the_local_store(tmp_path) -> None:
    store = ExperimentArtifactStore(tmp_path)

    with pytest.raises(ExperimentStorageError):
        store.write_json(
            relative_path="../outside.json",
            artifact_type="invalid",
            payload={},
        )


def test_running_lock_fails_fast_and_is_reusable_after_release(tmp_path) -> None:
    manager = ExperimentLockManager(tmp_path)
    first = manager.acquire("exp-lock")

    with pytest.raises(ExperimentLockError):
        manager.acquire("exp-lock")

    first.release()
    manager.acquire("exp-lock").release()


def test_registry_never_reuses_an_experiment_id_and_indexes_configuration(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    store = ExperimentArtifactStore(tmp_path)
    registry = ExperimentRegistry(store)
    environment = EnvironmentCollector().collect(
        application_version="1.0",
        dependency_names=("pydantic",),
    )
    now = datetime(2026, 7, 19, tzinfo=timezone.utc)

    registry.start(spec, environment, now)

    assert registry.load_spec(spec.experiment_id) == spec
    assert registry.experiments_for_configuration(spec.configuration_hash) == (
        spec.experiment_id,
    )
    with pytest.raises(DuplicateExperimentError):
        registry.start(spec, environment, now)


def test_explicit_recovery_closes_an_orphaned_running_attempt(tmp_path) -> None:
    dataset = make_experiment_dataset()
    spec = make_spec(dataset)
    registry = ExperimentRegistry(ExperimentArtifactStore(tmp_path))
    environment = EnvironmentCollector().collect(
        application_version="1.0",
        dependency_names=("pydantic",),
    )
    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    first = registry.start(spec, environment, now)

    recovered = registry.start(spec, environment, now, recover=True)
    history = registry.history(spec.experiment_id)

    assert recovered.attempt == 2
    assert recovered.recovered_from_run_id == first.run_id
    assert tuple(event.state.value for event in history) == (
        "running",
        "interrupted",
        "running",
    )
    assert history[1].execution_metadata[0].value == "orphaned_running_attempt"
