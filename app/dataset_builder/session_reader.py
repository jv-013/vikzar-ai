"""Read verified Ground Truth storage without changing its contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ground_truth.contracts import AlignedTrainingWindow, MeasuredEMGLabel, VerifiedSynchronizedTrainingSession
from app.ground_truth.exceptions import StorageError
from app.ground_truth.storage import GroundTruthSessionStorage

from .exceptions import DatasetInputError


class VerifiedSessionReader:
    """Load one checksum-verified Phase 2 artifact as its immutable contract."""

    def __init__(self, storage: GroundTruthSessionStorage | None = None) -> None:
        self._storage = storage or GroundTruthSessionStorage()

    def read(self, source: Path) -> VerifiedSynchronizedTrainingSession:
        """Verify and reconstruct one stored verified training session."""

        try:
            self._storage.verify(source)
            import pandas as pd

            session_payload = json.loads((source / "session.json").read_text(encoding="utf-8"))
            windows_frame = pd.read_parquet(source / "aligned_windows.parquet")
            labels_frame = pd.read_parquet(source / "labels.parquet")
            windows = tuple(self._window_from_row(row) for row in windows_frame.to_dict(orient="records"))
            labels = tuple(MeasuredEMGLabel.model_validate(row) for row in labels_frame.to_dict(orient="records"))
            self._validate_label_copy(session_payload, labels)
            return VerifiedSynchronizedTrainingSession.model_validate(
                {**session_payload, "aligned_windows": windows, "labels": labels}
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, StorageError) as exc:
            raise DatasetInputError(f"Unable to read verified Ground Truth session: {source}") from exc

    @staticmethod
    def _window_from_row(row: dict[str, Any]) -> AlignedTrainingWindow:
        payload = {
            "aligned_window_id": row["aligned_window_id"],
            "source_feature_vector_id": row["source_feature_vector_id"],
            "group_id": row["group_id"],
            "window_start_ms": row["window_start_ms"],
            "window_end_ms": row["window_end_ms"],
            "phase_segment_id": row["phase_segment_id"],
            "phase": row["phase"],
            "drill_id": VerifiedSessionReader._none_if_missing(row.get("drill_id")),
            "drill_protocol_version": VerifiedSessionReader._none_if_missing(
                row.get("drill_protocol_version")
            ),
            "smart_pod_features": json.loads(row["smart_pod_features_json"]),
            "emg_measurements": json.loads(row["emg_measurements_json"]),
            "synchronization": json.loads(row["synchronization_json"]),
        }
        return AlignedTrainingWindow.model_validate(payload)

    @staticmethod
    def _none_if_missing(value: Any) -> Any:
        """Convert Pandas null values back to JSON null without coercing text."""

        try:
            return None if value is None or value != value else value
        except TypeError:
            return value

    @staticmethod
    def _validate_label_copy(payload: dict[str, Any], labels: tuple[MeasuredEMGLabel, ...]) -> None:
        """Require JSON provenance and Parquet model targets to agree exactly."""

        if "labels" not in payload:
            raise DatasetInputError("Verified session JSON is missing direct EMG labels.")
        expected = sorted(
            json.dumps(item, sort_keys=True, separators=(",", ":")) for item in payload["labels"]
        )
        actual = sorted(
            json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            for item in labels
        )
        if actual != expected:
            raise DatasetInputError("Verified session label Parquet does not match session JSON provenance.")
