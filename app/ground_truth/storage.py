"""Atomic, checksum-verifiable persistence for verified ground-truth sessions."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .contracts.output import VerifiedSynchronizedTrainingSession
from .exceptions import StorageError


class GroundTruthSessionStorage:
    """Store immutable verified outputs as JSON and analysis-ready Parquet files."""

    _CHECKSUM_FILE = "checksums.json"
    _ARTIFACT_FILES = frozenset(
        {
            "aligned_windows.parquet",
            "labels.parquet",
            "session.json",
            "quality_report.json",
            "provenance.json",
        }
    )
    _WINDOW_COLUMNS = (
        "aligned_window_id",
        "source_feature_vector_id",
        "group_id",
        "window_start_ms",
        "window_end_ms",
        "phase_segment_id",
        "phase",
        "drill_id",
        "drill_protocol_version",
        "smart_pod_features_json",
        "emg_measurements_json",
        "synchronization_json",
    )
    _LABEL_COLUMNS = (
        "aligned_window_id",
        "group_id",
        "metric_name",
        "value",
        "amplitude_unit",
        "normalization_method",
        "source_feature_vector_id",
    )

    def write(self, session: VerifiedSynchronizedTrainingSession, destination: Path) -> None:
        """Atomically persist one verified session to a new destination folder.

        The destination is never overwritten.  A temporary sibling is removed
        on any failure, so consumers never observe a partial verified session.
        """

        destination = destination.resolve()
        if destination.exists():
            raise StorageError(f"Ground-truth destination already exists: {destination}")
        staging = destination.with_name(f".{destination.name}.staging-{uuid.uuid4().hex}")
        try:
            staging.mkdir(parents=True)
            self._write_parquet(session, staging)
            self._write_json(
                staging / "session.json",
                session.model_dump(mode="json", exclude={"aligned_windows"}),
            )
            self._write_json(staging / "quality_report.json", session.quality_report.model_dump(mode="json"))
            self._write_json(staging / "provenance.json", session.provenance.model_dump(mode="json"))
            self._write_manifest(staging)
            staging.rename(destination)
        except StorageError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except (OSError, ValueError, TypeError) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise StorageError(f"Unable to store verified ground-truth session: {destination}") from exc

    def verify(self, destination: Path) -> None:
        """Validate the checksum manifest and required output artifacts."""

        destination = destination.resolve()
        manifest_path = destination / self._CHECKSUM_FILE
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected = manifest["artifacts"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise StorageError(f"Ground-truth checksum manifest is invalid: {manifest_path}") from exc
        if manifest.get("algorithm") != "sha256" or set(expected) != self._ARTIFACT_FILES:
            raise StorageError("Ground-truth checksum manifest does not describe the required artifacts.")
        for filename, expected_hash in expected.items():
            actual_path = destination / filename
            if not actual_path.is_file() or self._sha256(actual_path) != expected_hash:
                raise StorageError(f"Ground-truth artifact checksum verification failed: {filename}")

    def _write_parquet(self, session: VerifiedSynchronizedTrainingSession, destination: Path) -> None:
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - dependency installation is environmental
            raise StorageError("Ground-truth Parquet storage requires pandas and pyarrow.") from exc
        try:
            pd.DataFrame(self._window_rows(session), columns=self._WINDOW_COLUMNS).to_parquet(
                destination / "aligned_windows.parquet", index=False
            )
            pd.DataFrame(self._label_rows(session), columns=self._LABEL_COLUMNS).to_parquet(
                destination / "labels.parquet", index=False
            )
        except (ImportError, ModuleNotFoundError, ValueError) as exc:
            raise StorageError("Ground-truth Parquet storage requires the pyarrow dependency.") from exc

    @staticmethod
    def _window_rows(session: VerifiedSynchronizedTrainingSession) -> list[dict[str, Any]]:
        """Flatten one accepted window per row without losing nested evidence."""

        return [
            {
                "aligned_window_id": window.aligned_window_id,
                "source_feature_vector_id": window.source_feature_vector_id,
                "group_id": window.group_id,
                "window_start_ms": window.window_start_ms,
                "window_end_ms": window.window_end_ms,
                "phase_segment_id": window.phase_segment_id,
                "phase": window.phase.value,
                "drill_id": window.drill_id,
                "drill_protocol_version": window.drill_protocol_version,
                "smart_pod_features_json": GroundTruthSessionStorage._canonical_json(
                    {name: value.model_dump(mode="json") for name, value in window.smart_pod_features.items()}
                ),
                "emg_measurements_json": GroundTruthSessionStorage._canonical_json(
                    window.emg_measurements.model_dump(mode="json")
                ),
                "synchronization_json": GroundTruthSessionStorage._canonical_json(
                    window.synchronization.model_dump(mode="json")
                ),
            }
            for window in session.aligned_windows
        ]

    @staticmethod
    def _label_rows(session: VerifiedSynchronizedTrainingSession) -> list[dict[str, Any]]:
        return [label.model_dump(mode="json") for label in session.labels]

    def _write_manifest(self, destination: Path) -> None:
        manifest = {
            "algorithm": "sha256",
            "artifacts": {
                filename: self._sha256(destination / filename)
                for filename in sorted(self._ARTIFACT_FILES)
            },
        }
        self._write_json(destination / self._CHECKSUM_FILE, manifest)

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(GroundTruthSessionStorage._canonical_json(payload) + "\n", encoding="utf-8")

    @staticmethod
    def _canonical_json(payload: object) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
