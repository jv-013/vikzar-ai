"""JSON ingestion for one offline, immutable ground-truth capture session."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.raw_feature_vector import RawFeatureVector

from .contracts.capture import (
    CalibrationSession,
    CaptureSession,
    DeviceMetadata,
    DrillEvent,
    EMGRecording,
    SensorPlacementRecord,
    TrainingPhaseSegment,
)
from .contracts.synchronization import SynchronizationAudit
from .exceptions import CaptureSessionError


class SourceArtifact(BaseModel):
    """Checksum-addressed JSON input declared by a capture manifest."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class CaptureIngestionManifest(BaseModel):
    """Manifest that binds all acquisition evidence to one capture identity."""

    model_config = ConfigDict(frozen=True)

    capture_session_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    captured_at: datetime
    sources: dict[str, SourceArtifact]


class GroundTruthCaptureIngestor:
    """Load checksum-verified acquisition JSON into the existing contract."""

    _REQUIRED_SOURCES = frozenset(
        {
            "session_metadata",
            "etl_exports",
            "emg_captures",
            "synchronization_audit",
            "drill_log",
            "placement_records",
        }
    )

    def load(self, manifest_path: Path) -> CaptureSession:
        """Load one manifest and construct its sole immutable CaptureSession.

        Source paths are always resolved relative to the manifest directory and
        may not escape it.  Each file is hashed before its JSON is parsed.
        """

        manifest_path = manifest_path.resolve()
        manifest_payload = self._read_json(manifest_path, "capture manifest")
        try:
            manifest = CaptureIngestionManifest.model_validate(manifest_payload)
        except ValidationError as exc:
            raise CaptureSessionError("Capture ingestion manifest is invalid.") from exc

        missing = self._REQUIRED_SOURCES - set(manifest.sources)
        unexpected = set(manifest.sources) - self._REQUIRED_SOURCES
        if missing or unexpected:
            details = []
            if missing:
                details.append(f"missing sources: {', '.join(sorted(missing))}")
            if unexpected:
                details.append(f"unexpected sources: {', '.join(sorted(unexpected))}")
            raise CaptureSessionError("Capture ingestion manifest has " + "; ".join(details) + ".")

        payloads: dict[str, Any] = {}
        source_hashes = {"capture_manifest": self._sha256(manifest_path)}
        for name, artifact in manifest.sources.items():
            source_path = self._resolve_source(manifest_path.parent, artifact.path)
            actual_hash = self._sha256(source_path)
            if actual_hash.lower() != artifact.sha256.lower():
                raise CaptureSessionError(f"Checksum mismatch for capture source '{name}'.")
            payloads[name] = self._read_json(source_path, name)
            source_hashes[name] = actual_hash

        metadata = payloads["session_metadata"]
        if not isinstance(metadata, dict):
            raise CaptureSessionError("session_metadata must contain one JSON object.")
        try:
            return CaptureSession(
                capture_session_id=manifest.capture_session_id,
                schema_version=manifest.schema_version,
                captured_at=manifest.captured_at,
                raw_feature_vectors=self._models(payloads["etl_exports"], RawFeatureVector, "etl_exports"),
                emg_recordings=self._models(payloads["emg_captures"], EMGRecording, "emg_captures"),
                synchronization_audit=SynchronizationAudit.model_validate(payloads["synchronization_audit"]),
                drill_events=self._models(payloads["drill_log"], DrillEvent, "drill_log"),
                placement_records=self._models(payloads["placement_records"], SensorPlacementRecord, "placement_records"),
                devices=self._models(metadata.get("devices"), DeviceMetadata, "session_metadata.devices"),
                calibration_sessions=self._models(
                    metadata.get("calibration_sessions"),
                    CalibrationSession,
                    "session_metadata.calibration_sessions",
                ),
                phases=self._models(metadata.get("phases"), TrainingPhaseSegment, "session_metadata.phases"),
                source_sha256=source_hashes,
            )
        except ValidationError as exc:
            raise CaptureSessionError("Ingested acquisition evidence does not form a valid CaptureSession.") from exc

    @staticmethod
    def _models(payload: Any, model: type[BaseModel], source_name: str) -> tuple[Any, ...]:
        if not isinstance(payload, list):
            raise CaptureSessionError(f"{source_name} must contain a JSON array.")
        try:
            return tuple(model.model_validate(item) for item in payload)
        except ValidationError as exc:
            raise CaptureSessionError(f"{source_name} contains an invalid record.") from exc

    @staticmethod
    def _read_json(path: Path, description: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CaptureSessionError(f"Unable to read {description} JSON: {path}") from exc

    @staticmethod
    def _sha256(path: Path) -> str:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise CaptureSessionError(f"Unable to read capture source: {path}") from exc

    @staticmethod
    def _resolve_source(root: Path, declared_path: str) -> Path:
        candidate = (root / declared_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise CaptureSessionError("Capture source paths must remain inside the manifest directory.") from exc
        if not candidate.is_file():
            raise CaptureSessionError(f"Capture source does not exist: {declared_path}")
        return candidate
