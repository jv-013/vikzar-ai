"""Thread-safe deterministic session lifecycle and local checkpoint recovery."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import ValidationError

from app.inference.contracts import InferencePrediction

from .contracts import (
    SessionCheckpoint,
    SessionLifecycleState,
    SessionSnapshot,
    SessionStartRequest,
)
from .exceptions import (
    SessionConflictError,
    SessionNotFoundError,
    SessionRecoveryError,
)


class SessionCheckpointStore(Protocol):
    """Local recoverable checkpoint boundary."""

    def save(self, checkpoint: SessionCheckpoint) -> None:
        """Persist one complete local session checkpoint."""

    def load(self, session_id: str) -> SessionCheckpoint | None:
        """Load and verify a local session checkpoint."""


class InMemorySessionCheckpointStore:
    """Thread-safe local store used by embedded deployments and tests."""

    def __init__(self) -> None:
        self._values: dict[str, SessionCheckpoint] = {}
        self._lock = RLock()

    def save(self, checkpoint: SessionCheckpoint) -> None:
        with self._lock:
            self._values[checkpoint.snapshot.session_id] = checkpoint.model_copy(
                deep=True
            )

    def load(self, session_id: str) -> SessionCheckpoint | None:
        with self._lock:
            value = self._values.get(session_id)
            return None if value is None else value.model_copy(deep=True)


class LocalSessionCheckpointStore:
    """Atomic checksum-protected local JSON checkpoints for process recovery."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def save(self, checkpoint: SessionCheckpoint) -> None:
        path = self._path(checkpoint.snapshot.session_id)
        payload = json.dumps(
            checkpoint.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        envelope = (
            json.dumps(
                {
                    "checksum": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    "payload": json.loads(payload),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        staging = path.with_name(f".{path.name}.staging-{uuid.uuid4().hex}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with staging.open("xb") as handle:
                handle.write(envelope)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(staging, path)
        except OSError as exc:
            raise SessionRecoveryError("Unable to persist local session checkpoint.") from exc
        finally:
            if staging.exists():
                staging.unlink(missing_ok=True)

    def load(self, session_id: str) -> SessionCheckpoint | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            payload = json.dumps(
                envelope["payload"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if (
                hashlib.sha256(payload.encode("utf-8")).hexdigest()
                != envelope["checksum"]
            ):
                raise SessionRecoveryError("Local session checkpoint checksum failed.")
            return SessionCheckpoint.model_validate(envelope["payload"])
        except SessionRecoveryError:
            raise
        except (OSError, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise SessionRecoveryError("Local session checkpoint is invalid.") from exc

    def _path(self, session_id: str) -> Path:
        if (
            not session_id
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in session_id)
            or len(session_id) > 128
        ):
            raise SessionRecoveryError("Session checkpoint ID is unsafe.")
        path = (self._root / f"{session_id}.json").resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise SessionRecoveryError("Session checkpoint path escaped its root.") from exc
        return path


class SessionManager:
    """Own deterministic transitions and local prediction history."""

    def __init__(
        self,
        store: SessionCheckpointStore,
        *,
        heartbeat_timeout_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._timeout = heartbeat_timeout_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions: dict[str, SessionCheckpoint] = {}
        self._processing_locks: dict[str, RLock] = {}
        self._lock = RLock()

    def start(self, request: SessionStartRequest) -> SessionSnapshot:
        session_id = request.session.session_id
        with self._lock:
            if session_id in self._sessions or self._store.load(session_id) is not None:
                raise SessionConflictError("Session ID has already been used.")
            now = self._now()
            snapshot = SessionSnapshot(
                session_id=session_id,
                player_id=request.player.player_id,
                state=SessionLifecycleState.ACTIVE,
                started_at=now,
                last_heartbeat_at=now,
                prediction_count=0,
                recovery_count=0,
            )
            checkpoint = SessionCheckpoint(
                snapshot=snapshot,
                player=request.player.model_copy(deep=True),
                session=request.session.model_copy(deep=True),
            )
            self._sessions[session_id] = checkpoint
            self._processing_locks[session_id] = RLock()
            self._store.save(checkpoint)
            return snapshot

    def get(self, session_id: str) -> SessionSnapshot:
        self._mark_one_stale(session_id)
        return self._checkpoint(session_id).snapshot

    def heartbeat(self, session_id: str) -> SessionSnapshot:
        self._mark_one_stale(session_id)
        with self._lock:
            checkpoint = self._checkpoint(session_id)
            self._require_state(checkpoint, SessionLifecycleState.ACTIVE)
            return self._update(
                checkpoint,
                snapshot=checkpoint.snapshot.model_copy(
                    update={"last_heartbeat_at": self._now()}
                ),
            ).snapshot

    def disconnect(self, session_id: str) -> SessionSnapshot:
        with self._lock:
            checkpoint = self._checkpoint(session_id)
            self._require_state(checkpoint, SessionLifecycleState.ACTIVE)
            return self._update(
                checkpoint,
                snapshot=checkpoint.snapshot.model_copy(
                    update={"state": SessionLifecycleState.DISCONNECTED}
                ),
            ).snapshot

    def reconnect(self, session_id: str) -> SessionSnapshot:
        with self._lock:
            checkpoint = self._checkpoint(session_id)
            self._require_state(checkpoint, SessionLifecycleState.DISCONNECTED)
            return self._update(
                checkpoint,
                snapshot=checkpoint.snapshot.model_copy(
                    update={
                        "state": SessionLifecycleState.ACTIVE,
                        "last_heartbeat_at": self._now(),
                    }
                ),
            ).snapshot

    def stop(self, session_id: str, *, reason: str) -> SessionSnapshot:
        with self._lock:
            checkpoint = self._checkpoint(session_id)
            if checkpoint.snapshot.state is SessionLifecycleState.STOPPED:
                raise SessionConflictError("Session is already stopped.")
            now = self._now()
            return self._update(
                checkpoint,
                snapshot=checkpoint.snapshot.model_copy(
                    update={
                        "state": SessionLifecycleState.STOPPED,
                        "last_heartbeat_at": now,
                        "ended_at": now,
                        "stop_reason": reason,
                    }
                ),
            ).snapshot

    def recover(self, session_id: str) -> SessionSnapshot:
        with self._lock:
            if session_id in self._sessions:
                raise SessionConflictError("Session is already loaded.")
            checkpoint = self._store.load(session_id)
            if checkpoint is None:
                raise SessionNotFoundError("Session checkpoint was not found.")
            if checkpoint.snapshot.state is SessionLifecycleState.STOPPED:
                raise SessionConflictError("Stopped sessions cannot be recovered.")
            now = self._now()
            recovered = checkpoint.model_copy(
                update={
                    "snapshot": checkpoint.snapshot.model_copy(
                        update={
                            "state": SessionLifecycleState.ACTIVE,
                            "last_heartbeat_at": now,
                            "recovery_count": checkpoint.snapshot.recovery_count + 1,
                        }
                    )
                }
            )
            self._sessions[session_id] = recovered
            self._processing_locks[session_id] = RLock()
            self._store.save(recovered)
            return recovered.snapshot

    def history(self, session_id: str) -> tuple[InferencePrediction, ...]:
        return self._checkpoint(session_id).predictions

    def metadata(self, session_id: str) -> SessionCheckpoint:
        return self._checkpoint(session_id).model_copy(deep=True)

    def append_predictions(
        self,
        session_id: str,
        predictions: tuple[InferencePrediction, ...],
    ) -> SessionSnapshot:
        with self._lock:
            checkpoint = self._checkpoint(session_id)
            self._require_state(checkpoint, SessionLifecycleState.ACTIVE)
            updated_predictions = checkpoint.predictions + predictions
            now = self._now()
            updated = checkpoint.model_copy(
                update={
                    "predictions": updated_predictions,
                    "snapshot": checkpoint.snapshot.model_copy(
                        update={
                            "last_heartbeat_at": now,
                            "prediction_count": len(updated_predictions),
                        }
                    ),
                }
            )
            return self._update(updated).snapshot

    @contextmanager
    def processing(self, session_id: str) -> Iterator[None]:
        self._mark_one_stale(session_id)
        with self._lock:
            self._checkpoint(session_id)
            lock = self._processing_locks[session_id]
        with lock:
            yield

    def shutdown(self) -> tuple[SessionSnapshot, ...]:
        stopped: list[SessionSnapshot] = []
        with self._lock:
            active_ids = tuple(
                session_id
                for session_id, checkpoint in self._sessions.items()
                if checkpoint.snapshot.state is not SessionLifecycleState.STOPPED
            )
        for session_id in active_ids:
            stopped.append(self.stop(session_id, reason="graceful_shutdown"))
        return tuple(stopped)

    def mark_stale_disconnected(self) -> tuple[SessionSnapshot, ...]:
        """Move heartbeat-expired active sessions to disconnected exactly once."""

        now = self._now()
        stale: list[SessionSnapshot] = []
        with self._lock:
            session_ids = tuple(
                session_id
                for session_id, checkpoint in self._sessions.items()
                if checkpoint.snapshot.state is SessionLifecycleState.ACTIVE
                and (
                    now - checkpoint.snapshot.last_heartbeat_at
                ).total_seconds()
                > self._timeout
            )
        for session_id in session_ids:
            stale.append(self.disconnect(session_id))
        return tuple(stale)

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                checkpoint.snapshot.state is SessionLifecycleState.ACTIVE
                for checkpoint in self._sessions.values()
            )

    def _checkpoint(self, session_id: str) -> SessionCheckpoint:
        with self._lock:
            checkpoint = self._sessions.get(session_id)
            if checkpoint is None:
                raise SessionNotFoundError("Session was not found.")
            return checkpoint

    def _mark_one_stale(self, session_id: str) -> None:
        with self._lock:
            checkpoint = self._sessions.get(session_id)
            if checkpoint is None:
                return
            if (
                checkpoint.snapshot.state is SessionLifecycleState.ACTIVE
                and (
                    self._now() - checkpoint.snapshot.last_heartbeat_at
                ).total_seconds()
                > self._timeout
            ):
                self._update(
                    checkpoint,
                    snapshot=checkpoint.snapshot.model_copy(
                        update={"state": SessionLifecycleState.DISCONNECTED}
                    ),
                )

    def _update(
        self,
        checkpoint: SessionCheckpoint,
        *,
        snapshot: SessionSnapshot | None = None,
    ) -> SessionCheckpoint:
        updated = (
            checkpoint
            if snapshot is None
            else checkpoint.model_copy(update={"snapshot": snapshot})
        )
        self._sessions[updated.snapshot.session_id] = updated
        self._store.save(updated)
        return updated

    @staticmethod
    def _require_state(
        checkpoint: SessionCheckpoint,
        expected: SessionLifecycleState,
    ) -> None:
        if checkpoint.snapshot.state is not expected:
            raise SessionConflictError(
                f"Session must be {expected.value} for this transition."
            )

    def _now(self) -> datetime:
        value = self._clock()
        if value.utcoffset() is None:
            raise SessionConflictError("Session clock must return timezone-aware values.")
        return value
