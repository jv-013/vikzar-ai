"""Persisted ground-truth artifact tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("pyarrow", reason="Parquet contract requires pyarrow")

from app.ground_truth import GroundTruthSessionBuilder, GroundTruthSessionStorage
from app.ground_truth.exceptions import StorageError

from .helpers import make_capture
from .test_ingestion import _write_manifest


def test_writes_checksum_verified_json_and_parquet_artifacts(tmp_path: Path) -> None:
    """Accepted windows and direct labels are stored in their own Parquet data sets."""

    output = GroundTruthSessionBuilder().build(make_capture())
    destination = tmp_path / output.verified_session_id
    storage = GroundTruthSessionStorage()

    storage.write(output, destination)
    storage.verify(destination)

    assert set(path.name for path in destination.iterdir()) == {
        "aligned_windows.parquet",
        "labels.parquet",
        "session.json",
        "quality_report.json",
        "provenance.json",
        "checksums.json",
    }
    assert len(pd.read_parquet(destination / "aligned_windows.parquet")) == 1
    assert len(pd.read_parquet(destination / "labels.parquet")) == 2


def test_detects_tampered_persisted_artifact(tmp_path: Path) -> None:
    """Consumers can verify persisted output before dataset construction."""

    output = GroundTruthSessionBuilder().build(make_capture())
    destination = tmp_path / output.verified_session_id
    storage = GroundTruthSessionStorage()
    storage.write(output, destination)
    (destination / "session.json").write_text("{}", encoding="utf-8")

    with pytest.raises(StorageError, match="checksum verification failed"):
        storage.verify(destination)


def test_removes_partial_staging_data_when_storage_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed write never exposes an incomplete destination to consumers."""

    output = GroundTruthSessionBuilder().build(make_capture())
    destination = tmp_path / output.verified_session_id
    storage = GroundTruthSessionStorage()

    def fail_parquet(*_: object) -> None:
        raise StorageError("simulated parquet failure")

    monkeypatch.setattr(storage, "_write_parquet", fail_parquet)
    with pytest.raises(StorageError, match="simulated parquet failure"):
        storage.write(output, destination)

    assert not destination.exists()
    assert not list(tmp_path.glob("*.staging-*"))


def test_end_to_end_ingests_builds_and_persists_verified_ground_truth(tmp_path: Path) -> None:
    """The offline path is ingestion, verification, direct labels, then storage."""

    from app.ground_truth import GroundTruthCaptureIngestor

    capture = GroundTruthCaptureIngestor().load(_write_manifest(tmp_path))
    output = GroundTruthSessionBuilder().build(capture)
    destination = tmp_path / "output"

    storage = GroundTruthSessionStorage()
    storage.write(output, destination)
    storage.verify(destination)

    assert output.quality_report.accepted_count == 1
    assert len(pd.read_parquet(destination / "labels.parquet")) == 2
