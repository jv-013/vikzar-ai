"""Capture-side synchronization evidence for verified ground truth."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SynchronizationStatus(str, Enum):
    """Outcome of matching a Smart Pod observation to EMG evidence."""

    MATCHED = "matched"
    TIMED_OUT = "timed_out"
    ORPHANED = "orphaned"
    NOT_RECORDED = "not_recorded"


class SynchronizationObservation(BaseModel):
    """Synchronization evidence for one ETL feature vector and limb group."""

    model_config = ConfigDict(frozen=True)

    feature_vector_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    status: SynchronizationStatus
    primary_timestamp_ms: float
    emg_timestamp_ms: float | None = None
    alignment_error_ms: float | None = Field(default=None, ge=0)
    clock_reset_observed: bool = False

    @model_validator(mode="after")
    def validate_match_evidence(self) -> "SynchronizationObservation":
        """Require two timestamps and an error whenever a match is claimed."""

        if self.status is SynchronizationStatus.MATCHED:
            if self.emg_timestamp_ms is None or self.alignment_error_ms is None:
                raise ValueError("Matched synchronization requires EMG timestamp and alignment error.")
        elif self.alignment_error_ms is not None:
            raise ValueError("Only matched synchronization may define alignment_error_ms.")
        return self


class SynchronizationAudit(BaseModel):
    """Immutable session-level audit emitted by the acquisition workflow."""

    model_config = ConfigDict(frozen=True)

    audit_id: str = Field(min_length=1)
    clock_reference: str = Field(min_length=1)
    tolerance_ms: float = Field(gt=0)
    observations: tuple[SynchronizationObservation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_observation_keys(self) -> "SynchronizationAudit":
        """Require at most one synchronization finding for each vector/group pair."""

        keys = [(item.feature_vector_id, item.group_id) for item in self.observations]
        if len(set(keys)) != len(keys):
            raise ValueError("Synchronization observations must be unique per vector and group.")
        return self
