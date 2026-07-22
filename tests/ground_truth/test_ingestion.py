"""Offline capture ingestion tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.ground_truth import GroundTruthCaptureIngestor
from app.ground_truth.exceptions import CaptureSessionError

from .helpers import make_capture


def _write_json(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(directory: Path) -> Path:
    capture = make_capture()
    metadata = {
        "devices": [item.model_dump(mode="json") for item in capture.devices],
        "calibration_sessions": [item.model_dump(mode="json") for item in capture.calibration_sessions],
        "phases": [item.model_dump(mode="json") for item in capture.phases],
    }
    sources = {
        "session_metadata": _write_json(directory / "metadata.json", metadata),
        "etl_exports": _write_json(
            directory / "etl.json", [item.model_dump(mode="json") for item in capture.raw_feature_vectors]
        ),
        "emg_captures": _write_json(
            directory / "emg.json", [item.model_dump(mode="json") for item in capture.emg_recordings]
        ),
        "synchronization_audit": _write_json(
            directory / "audit.json", capture.synchronization_audit.model_dump(mode="json")
        ),
        "drill_log": _write_json(directory / "drills.json", []),
        "placement_records": _write_json(
            directory / "placements.json", [item.model_dump(mode="json") for item in capture.placement_records]
        ),
    }
    filenames = {
        "session_metadata": "metadata.json",
        "etl_exports": "etl.json",
        "emg_captures": "emg.json",
        "synchronization_audit": "audit.json",
        "drill_log": "drills.json",
        "placement_records": "placements.json",
    }
    manifest = {
        "capture_session_id": capture.capture_session_id,
        "schema_version": capture.schema_version,
        "captured_at": capture.captured_at.isoformat(),
        "sources": {name: {"path": filenames[name], "sha256": checksum} for name, checksum in sources.items()},
    }
    manifest_path = directory / "capture_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def test_loads_all_checksum_verified_capture_evidence(tmp_path: Path) -> None:
    """The ingestor creates the existing immutable CaptureSession contract."""

    capture = GroundTruthCaptureIngestor().load(_write_manifest(tmp_path))

    assert capture.capture_session_id == "capture-1"
    assert len(capture.raw_feature_vectors) == 1
    assert len(capture.emg_recordings) == 1
    assert set(capture.source_sha256) == {
        "capture_manifest",
        "session_metadata",
        "etl_exports",
        "emg_captures",
        "synchronization_audit",
        "drill_log",
        "placement_records",
    }


def test_rejects_changed_source_before_constructing_capture(tmp_path: Path) -> None:
    """A captured-source checksum is verified before its content is trusted."""

    manifest_path = _write_manifest(tmp_path)
    (tmp_path / "etl.json").write_text("[]", encoding="utf-8")

    with pytest.raises(CaptureSessionError, match="Checksum mismatch"):
        GroundTruthCaptureIngestor().load(manifest_path)
