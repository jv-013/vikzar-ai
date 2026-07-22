"""End-to-end local storage tests for Phase 3 datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.dataset_builder import DatasetBuildSpec, DatasetBuilder, DatasetStorage, VerifiedSessionReader
from app.dataset_builder.exceptions import DatasetStorageError
from app.ground_truth import GroundTruthSessionStorage

from .helpers import make_verified_session


pytest.importorskip("pyarrow", reason="Dataset storage requires the declared Parquet dependency")


def _result() -> object:
    return DatasetBuilder().build(
        [make_verified_session()],
        DatasetBuildSpec(
            dataset_name="synthetic-emg-training",
            target_metric_names=("quadriceps_rms", "hamstring_rms"),
        ),
    )


def test_writes_and_verifies_versioned_dataset_artifacts(tmp_path: Path) -> None:
    """Features, labels, manifest, and checksum evidence are stored locally."""

    result = _result()
    destination = tmp_path / result.dataset.dataset_id  # type: ignore[attr-defined]
    storage = DatasetStorage()
    storage.write(result, destination)  # type: ignore[arg-type]
    storage.verify(destination)

    manifest = storage.read_manifest(destination)
    assert manifest.dataset_id == result.dataset.dataset_id  # type: ignore[attr-defined]
    assert set(path.name for path in destination.iterdir()) == {
        "features.parquet",
        "labels.parquet",
        "dataset.json",
        "checksums.json",
    }
    assert "feature__motion__peak_resultant_acceleration" in pd.read_parquet(
        destination / "features.parquet"
    ).columns
    assert "target__quadriceps_rms" in pd.read_parquet(destination / "labels.parquet").columns


def test_rejects_tampered_dataset_artifact(tmp_path: Path) -> None:
    """Consumers must not use a dataset whose stored evidence has changed."""

    result = _result()
    destination = tmp_path / result.dataset.dataset_id  # type: ignore[attr-defined]
    storage = DatasetStorage()
    storage.write(result, destination)  # type: ignore[arg-type]
    (destination / "dataset.json").write_text("{}", encoding="utf-8")

    with pytest.raises(DatasetStorageError, match="checksum verification failed"):
        storage.verify(destination)


def test_removes_partial_dataset_when_storage_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed write never exposes a partial training dataset folder."""

    result = _result()
    destination = tmp_path / result.dataset.dataset_id  # type: ignore[attr-defined]
    storage = DatasetStorage()

    def fail_parquet(*_: object) -> None:
        raise DatasetStorageError("simulated parquet failure")

    monkeypatch.setattr(storage, "_write_parquet", fail_parquet)
    with pytest.raises(DatasetStorageError, match="simulated parquet failure"):
        storage.write(result, destination)  # type: ignore[arg-type]

    assert not destination.exists()
    assert not list(tmp_path.glob("*.staging-*"))


def test_end_to_end_reads_phase_two_artifact_then_persists_phase_three_dataset(tmp_path: Path) -> None:
    """Synthetic and real sessions share the same stored-contract path."""

    verified_session = make_verified_session()
    phase_two_path = tmp_path / "verified-session"
    GroundTruthSessionStorage().write(verified_session, phase_two_path)

    loaded = VerifiedSessionReader().read(phase_two_path)
    result = DatasetBuilder().build(
        [loaded],
        DatasetBuildSpec(
            dataset_name="synthetic-emg-training",
            target_metric_names=("quadriceps_rms", "hamstring_rms"),
        ),
    )
    destination = tmp_path / "dataset"
    storage = DatasetStorage()
    storage.write(result, destination)
    storage.verify(destination)

    assert result.dataset.sources[0].verified_session_id == verified_session.verified_session_id


def test_same_phase_two_inputs_produce_byte_identical_dataset_artifacts(tmp_path: Path) -> None:
    """Offline rebuilding is reproducible, including manifests and checksums."""

    result = _result()
    storage = DatasetStorage()
    first = tmp_path / "first"
    second = tmp_path / "second"
    storage.write(result, first)  # type: ignore[arg-type]
    storage.write(result, second)  # type: ignore[arg-type]

    for filename in ("features.parquet", "labels.parquet", "dataset.json", "checksums.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
