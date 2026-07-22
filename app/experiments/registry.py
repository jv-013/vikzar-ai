"""Append-only local lifecycle history for reproducible experiments."""

from __future__ import annotations

import re
from datetime import datetime

from .artifact_store import ExperimentArtifactStore
from .contracts import (
    ArtifactReference,
    ExecutionEnvironment,
    ExperimentLifecycleState,
    ExperimentRun,
    ExperimentSpec,
    MetadataValue,
)
from .exceptions import (
    DuplicateExperimentError,
    ExperimentCompatibilityError,
    ExperimentStorageError,
)


class ExperimentRegistry:
    """Persist immutable specs and lifecycle events and support explicit recovery."""

    def __init__(self, artifact_store: ExperimentArtifactStore) -> None:
        self._store = artifact_store

    def start(
        self,
        spec: ExperimentSpec,
        environment: ExecutionEnvironment,
        now: datetime,
        *,
        recover: bool = False,
    ) -> ExperimentRun:
        """Register a unique experiment or resume its interrupted/failed history."""

        history = self.history(spec.experiment_id)
        registered = self.load_spec(spec.experiment_id)
        if recover:
            if registered is None or not history:
                raise DuplicateExperimentError(
                    f"Experiment '{spec.experiment_id}' has no recoverable history."
                )
            if registered != spec:
                raise ExperimentCompatibilityError(
                    "Recovery requires the exact immutable experiment specification."
                )
            latest = self._latest(history)
            if latest.state is ExperimentLifecycleState.COMPLETED:
                raise DuplicateExperimentError(
                    f"Experiment '{spec.experiment_id}' cannot recover from "
                    f"'{latest.state.value}'."
                )
            if latest.state is ExperimentLifecycleState.RUNNING:
                self.record(
                    self.interrupted(
                        latest,
                        now,
                        (
                            MetadataValue(
                                name="recovery_reason",
                                value="orphaned_running_attempt",
                            ),
                        ),
                    )
                )
            attempt = latest.attempt + 1
            recovered_from = latest.run_id
        else:
            if registered is not None or history:
                raise DuplicateExperimentError(
                    f"Experiment ID '{spec.experiment_id}' has already been used."
                )
            self._register_spec(spec)
            attempt = 1
            recovered_from = None

        run = ExperimentRun(
            run_id=f"{spec.experiment_id}:attempt:{attempt}",
            experiment_id=spec.experiment_id,
            configuration_hash=spec.configuration_hash,
            attempt=attempt,
            state=ExperimentLifecycleState.RUNNING,
            started_at=now,
            recovered_from_run_id=recovered_from,
            environment=environment,
        )
        self.record(run)
        return run

    def record(self, run: ExperimentRun) -> None:
        """Append an immutable lifecycle snapshot, rejecting any conflicting event."""

        filename = (
            f"registry/{run.experiment_id}/"
            f"attempt-{run.attempt:04d}-{run.state.value}.json"
        )
        self._store.write_json(
            relative_path=filename,
            artifact_type="experiment_run",
            payload=run,
        )

    def history(self, experiment_id: str) -> tuple[ExperimentRun, ...]:
        """Read every immutable lifecycle snapshot for one experiment in order."""

        directory = self._store.root / "registry" / experiment_id
        if not directory.exists():
            return ()
        try:
            parsed = tuple(
                ExperimentRun.model_validate_json(path.read_text(encoding="utf-8"))
                for path in sorted(directory.glob("attempt-*.json"))
            )
        except (OSError, ValueError) as exc:
            raise ExperimentStorageError(
                f"Experiment registry history is invalid: {experiment_id}"
            ) from exc
        event_order = {
            ExperimentLifecycleState.RUNNING: 0,
            ExperimentLifecycleState.COMPLETED: 1,
            ExperimentLifecycleState.INTERRUPTED: 1,
            ExperimentLifecycleState.FAILED: 1,
        }
        return tuple(
            sorted(parsed, key=lambda run: (run.attempt, event_order[run.state]))
        )

    def load_spec(self, experiment_id: str) -> ExperimentSpec | None:
        """Load the permanent specification registered for an experiment ID."""

        relative_path = f"registry/{experiment_id}/spec.json"
        path = self._store.root / relative_path
        if not path.exists():
            return None
        try:
            return ExperimentSpec.model_validate(self._store.read_json(relative_path))
        except ValueError as exc:
            raise ExperimentStorageError(
                f"Experiment specification is invalid: {experiment_id}"
            ) from exc

    def experiments_for_configuration(self, configuration_hash: str) -> tuple[str, ...]:
        """Return permanent experiment IDs sharing one deterministic configuration."""

        if re.fullmatch(r"[A-Fa-f0-9]{64}", configuration_hash) is None:
            raise ExperimentStorageError("Configuration hash must be a SHA-256 value.")
        directory = self._store.root / "configuration_index" / configuration_hash
        if not directory.exists():
            return ()
        return tuple(sorted(path.stem for path in directory.glob("*.json")))

    def _register_spec(self, spec: ExperimentSpec) -> None:
        self._store.write_json(
            relative_path=f"registry/{spec.experiment_id}/spec.json",
            artifact_type="experiment_spec",
            payload=spec,
        )
        self._store.write_json(
            relative_path=(
                f"configuration_index/{spec.configuration_hash}/"
                f"{spec.experiment_id}.json"
            ),
            artifact_type="configuration_index",
            payload={
                "configuration_hash": spec.configuration_hash,
                "experiment_id": spec.experiment_id,
            },
        )

    @staticmethod
    def interrupted(
        run: ExperimentRun,
        now: datetime,
        metadata: tuple[MetadataValue, ...],
    ) -> ExperimentRun:
        """Create the immutable interrupted terminal snapshot for an attempt."""

        return run.model_copy(
            update={
                "state": ExperimentLifecycleState.INTERRUPTED,
                "ended_at": now,
                "execution_metadata": metadata,
            }
        )

    @staticmethod
    def failed(
        run: ExperimentRun,
        now: datetime,
        metadata: tuple[MetadataValue, ...],
    ) -> ExperimentRun:
        """Create the immutable failed terminal snapshot for an attempt."""

        return run.model_copy(
            update={
                "state": ExperimentLifecycleState.FAILED,
                "ended_at": now,
                "execution_metadata": metadata,
            }
        )

    @staticmethod
    def completed(
        run: ExperimentRun,
        now: datetime,
        metadata: tuple[MetadataValue, ...],
        artifact_references: tuple[ArtifactReference, ...],
    ) -> ExperimentRun:
        """Create the immutable completed terminal snapshot for an attempt."""

        return run.model_copy(
            update={
                "state": ExperimentLifecycleState.COMPLETED,
                "ended_at": now,
                "execution_metadata": metadata,
                "artifact_references": artifact_references,
            }
        )

    @staticmethod
    def _latest(history: tuple[ExperimentRun, ...]) -> ExperimentRun:
        priority = {
            ExperimentLifecycleState.RUNNING: 0,
            ExperimentLifecycleState.COMPLETED: 1,
            ExperimentLifecycleState.INTERRUPTED: 1,
            ExperimentLifecycleState.FAILED: 1,
        }
        return max(history, key=lambda run: (run.attempt, priority[run.state]))
