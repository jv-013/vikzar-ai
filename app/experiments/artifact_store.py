"""Checksum-addressed immutable local artifact storage for experiments."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from .contracts import ArtifactReference
from .exceptions import ExperimentStorageError


class ExperimentArtifactStore:
    """Persist JSON artifacts locally without overwriting prior experiment evidence."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @property
    def root(self) -> Path:
        """Return the local root used for immutable experiment evidence."""

        return self._root

    def write_json(self, *, relative_path: str, artifact_type: str, payload: object) -> ArtifactReference:
        """Write canonical JSON once and return its checksum-addressed reference."""

        encoded = self._canonical_json(payload).encode("utf-8")
        return self.write_bytes(
            relative_path=relative_path,
            artifact_type=artifact_type,
            payload=encoded,
            media_type="application/json",
        )

    def write_bytes(
        self,
        *,
        relative_path: str,
        artifact_type: str,
        payload: bytes,
        media_type: str = "application/octet-stream",
    ) -> ArtifactReference:
        """Atomically persist immutable bytes and return their stable reference."""

        path = self._resolve(relative_path)
        staging: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                existing = path.read_bytes()
                if existing != payload:
                    raise ExperimentStorageError(f"Immutable artifact already exists: {relative_path}")
            else:
                staging = path.with_name(f".{path.name}.staging-{uuid.uuid4().hex}")
                with staging.open("xb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                staging.rename(path)
        except ExperimentStorageError:
            raise
        except OSError as exc:
            raise ExperimentStorageError(f"Unable to persist experiment artifact: {relative_path}") from exc
        finally:
            if staging is not None and staging.exists():
                try:
                    staging.unlink()
                except OSError:
                    pass
        checksum = hashlib.sha256(payload).hexdigest()
        return ArtifactReference(
            artifact_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"artifact:{relative_path}:{checksum}")),
            artifact_type=artifact_type,
            relative_path=Path(relative_path).as_posix(),
            sha256=checksum,
            media_type=media_type,
        )

    def verify(self, reference: ArtifactReference) -> None:
        """Verify a referenced local artifact exists and retains its declared checksum."""

        path = self._resolve(reference.relative_path)
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise ExperimentStorageError(f"Referenced artifact is unavailable: {reference.relative_path}") from exc
        if actual != reference.sha256:
            raise ExperimentStorageError(f"Referenced artifact checksum failed: {reference.relative_path}")

    def read_json(self, relative_path: str) -> Any:
        """Read one previously stored JSON artifact after resolving its safe local path."""

        try:
            return json.loads(self._resolve(relative_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExperimentStorageError(f"Unable to read experiment artifact: {relative_path}") from exc

    def read_bytes(self, relative_path: str) -> bytes:
        """Read one immutable binary artifact from the local store."""

        try:
            return self._resolve(relative_path).read_bytes()
        except OSError as exc:
            raise ExperimentStorageError(f"Unable to read experiment artifact: {relative_path}") from exc

    def _resolve(self, relative_path: str) -> Path:
        path = (self._root / relative_path).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise ExperimentStorageError("Experiment artifact paths must remain inside the local store.") from exc
        return path

    @staticmethod
    def _canonical_json(payload: object) -> str:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
