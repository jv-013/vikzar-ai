"""Atomic local persistence for immutable versioned training datasets."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .builder import DatasetBuildResult
from .contracts import TrainingExample, VersionedTrainingDataset
from .exceptions import DatasetStorageError


class DatasetStorage:
    """Write and verify local Phase 3 dataset artifacts without cloud services."""

    _CHECKSUM_FILE = "checksums.json"
    _ARTIFACT_FILES = frozenset({"features.parquet", "labels.parquet", "dataset.json"})
    _FEATURE_ID_COLUMNS = (
        "example_id",
        "verified_session_id",
        "capture_session_id",
        "player_id",
        "session_id",
        "group_id",
        "source_feature_vector_id",
        "aligned_window_id",
        "split",
    )

    def write(self, result: DatasetBuildResult, destination: Path) -> None:
        """Atomically persist a new dataset folder and its checksum manifest."""

        destination = destination.resolve()
        if destination.exists():
            raise DatasetStorageError(f"Dataset destination already exists: {destination}")
        staging = destination.with_name(f".{destination.name}.staging-{uuid.uuid4().hex}")
        try:
            staging.mkdir(parents=True)
            self._validate_result(result)
            self._write_parquet(result, staging)
            self._write_json(staging / "dataset.json", result.dataset.model_dump(mode="json"))
            self._write_manifest(staging)
            staging.rename(destination)
        except DatasetStorageError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except (OSError, ValueError, TypeError) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise DatasetStorageError(f"Unable to persist training dataset: {destination}") from exc

    def verify(self, destination: Path) -> None:
        """Verify all required immutable dataset artifacts against their hashes."""

        destination = destination.resolve()
        try:
            manifest = json.loads((destination / self._CHECKSUM_FILE).read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DatasetStorageError("Dataset checksum manifest is invalid.") from exc
        if manifest.get("algorithm") != "sha256" or set(artifacts) != self._ARTIFACT_FILES:
            raise DatasetStorageError("Dataset checksum manifest does not describe the required artifacts.")
        for filename, expected_hash in artifacts.items():
            path = destination / filename
            if not path.is_file() or self._sha256(path) != expected_hash:
                raise DatasetStorageError(f"Dataset artifact checksum verification failed: {filename}")

    def read_manifest(self, destination: Path) -> VersionedTrainingDataset:
        """Return a verified dataset manifest without loading all training rows."""

        self.verify(destination)
        try:
            return VersionedTrainingDataset.model_validate_json(
                (destination / "dataset.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise DatasetStorageError("Dataset manifest cannot be parsed.") from exc

    def _write_parquet(self, result: DatasetBuildResult, destination: Path) -> None:
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - dependency installation is environmental
            raise DatasetStorageError("Dataset Parquet storage requires pandas and pyarrow.") from exc
        feature_columns = self._FEATURE_ID_COLUMNS + result.dataset.feature_schema.feature_names
        label_columns = ("example_id",) + result.dataset.feature_schema.target_names
        try:
            pd.DataFrame(
                [self._feature_row(example) for example in result.examples], columns=feature_columns
            ).to_parquet(destination / "features.parquet", index=False)
            pd.DataFrame(
                [self._label_row(example) for example in result.examples], columns=label_columns
            ).to_parquet(destination / "labels.parquet", index=False)
        except (ImportError, ModuleNotFoundError, ValueError) as exc:
            raise DatasetStorageError("Dataset Parquet storage requires the pyarrow dependency.") from exc

    @staticmethod
    def _feature_row(example: TrainingExample) -> dict[str, Any]:
        row: dict[str, Any] = {
            "example_id": example.example_id,
            "verified_session_id": example.verified_session_id,
            "capture_session_id": example.capture_session_id,
            "player_id": example.player_id,
            "session_id": example.session_id,
            "group_id": example.group_id,
            "source_feature_vector_id": example.source_feature_vector_id,
            "aligned_window_id": example.aligned_window_id,
            "split": example.split.value,
        }
        row.update({item.name: item.value for item in example.features})
        return row

    @staticmethod
    def _label_row(example: TrainingExample) -> dict[str, Any]:
        return {"example_id": example.example_id} | {
            item.name: item.value for item in example.targets
        }

    def _write_manifest(self, destination: Path) -> None:
        self._write_json(
            destination / self._CHECKSUM_FILE,
            {
                "algorithm": "sha256",
                "artifacts": {
                    filename: self._sha256(destination / filename)
                    for filename in sorted(self._ARTIFACT_FILES)
                },
            },
        )

    @staticmethod
    def _validate_result(result: DatasetBuildResult) -> None:
        if result.dataset.example_count != len(result.examples):
            raise DatasetStorageError("Dataset manifest example count does not match its examples.")
        schema = result.dataset.feature_schema
        for example in result.examples:
            if tuple(item.name for item in example.features) != schema.feature_names:
                raise DatasetStorageError("Dataset example feature schema does not match dataset manifest.")
            if tuple(item.name for item in example.targets) != schema.target_names:
                raise DatasetStorageError("Dataset example target schema does not match dataset manifest.")

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
