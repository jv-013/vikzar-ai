"""Exclusive per-experiment filesystem locking for local orchestration."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from .exceptions import ExperimentLockError, ExperimentStorageError


class ExperimentLock:
    """Own one atomically created ``running.lock`` for an experiment ID."""

    def __init__(self, path: Path, owner_token: str) -> None:
        self._path = path
        self._owner_token = owner_token
        self._released = False

    def __enter__(self) -> "ExperimentLock":
        """Return the already-acquired lock lease."""

        return self

    def __exit__(self, *_: object) -> None:
        """Release only the lock created by this lease."""

        self.release()

    def release(self) -> None:
        """Remove the lock when its on-disk owner token still matches."""

        if self._released:
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if payload.get("owner_token") != self._owner_token:
                raise ExperimentLockError("Experiment lock ownership changed before release.")
            self._path.unlink()
        except ExperimentLockError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExperimentStorageError("Unable to release the experiment lock safely.") from exc
        finally:
            self._released = True


class ExperimentLockManager:
    """Acquire fail-fast cross-process locks using atomic local file creation."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def acquire(self, experiment_id: str) -> ExperimentLock:
        """Create ``registry/<experiment_id>/running.lock`` or fail immediately."""

        directory = (self._root / "registry" / experiment_id).resolve()
        try:
            directory.relative_to(self._root)
        except ValueError as exc:
            raise ExperimentLockError("Experiment lock path must remain inside its local store.") from exc
        path = directory / "running.lock"
        owner_token = uuid.uuid4().hex
        payload = (
            json.dumps(
                {
                    "experiment_id": experiment_id,
                    "owner_token": owner_token,
                    "process_id": os.getpid(),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        descriptor: int | None = None
        created = False
        try:
            directory.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            created = True
            os.write(descriptor, payload)
            os.fsync(descriptor)
        except FileExistsError as exc:
            raise ExperimentLockError(
                f"Experiment '{experiment_id}' is already locked by an active execution."
            ) from exc
        except OSError as exc:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                descriptor = None
            if created:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise ExperimentStorageError("Unable to acquire the experiment lock.") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
        return ExperimentLock(path, owner_token)
