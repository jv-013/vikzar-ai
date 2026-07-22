"""Immutable acquisition-side contracts for one training capture session."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.raw_feature_vector import RawFeatureVector

from .synchronization import SynchronizationAudit


class TrainingPhase(str, Enum):
    """The controlled portions of a training session."""

    CALIBRATION = "calibration"
    WARM_UP = "warm_up"
    DRILL = "drill"
    RECOVERY = "recovery"
    COOL_DOWN = "cool_down"


class DeviceMetadata(BaseModel):
    """Immutable identity and role of one device used during capture."""

    model_config = ConfigDict(frozen=True)

    device_id: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
    serial_number: str = Field(min_length=1)
    firmware_revision: str = Field(min_length=1)
    hardware_revision: str = Field(min_length=1)


class SensorPlacementRecord(BaseModel):
    """Recorded Smart Pod or EMG placement for one capture device."""

    model_config = ConfigDict(frozen=True)

    device_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    body_side: str = Field(pattern="^(left|right)$")
    anatomical_location: str = Field(min_length=1)
    orientation_description: str = Field(min_length=1)
    fixation_description: str = Field(min_length=1)
    channel_to_muscle: dict[str, str] = Field(default_factory=dict)
    placement_verified: bool
    verified_by: str = Field(min_length=1)


class EMGRecording(BaseModel):
    """Acquisition metadata for a recorded EMG stream, never a prediction."""

    model_config = ConfigDict(frozen=True)

    recording_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    sampling_rate_hz: float = Field(gt=0)
    amplitude_unit: str = Field(min_length=1)
    normalization_method: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)


class CalibrationSession(BaseModel):
    """A documented calibration or EMG reference procedure within capture."""

    model_config = ConfigDict(frozen=True)

    calibration_id: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime
    procedure: str = Field(min_length=1)
    normalization_method: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    reference_values: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time_range(self) -> "CalibrationSession":
        """Require calibration end time to follow its start time."""

        if self.ended_at <= self.started_at:
            raise ValueError("CalibrationSession.ended_at must follow started_at.")
        return self


class TrainingPhaseSegment(BaseModel):
    """A time-bounded calibration, warm-up, drill, recovery, or cooldown block."""

    model_config = ConfigDict(frozen=True)

    segment_id: str = Field(min_length=1)
    phase: TrainingPhase
    started_at: datetime
    ended_at: datetime
    drill_id: str | None = None
    drill_protocol_version: str | None = None
    intensity_instruction: str | None = None

    @model_validator(mode="after")
    def validate_segment(self) -> "TrainingPhaseSegment":
        """Validate duration and require a versioned drill definition for drills."""

        if self.ended_at <= self.started_at:
            raise ValueError("TrainingPhaseSegment.ended_at must follow started_at.")
        if self.phase is TrainingPhase.DRILL and (
            not self.drill_id or not self.drill_protocol_version
        ):
            raise ValueError("Drill segments require drill_id and drill_protocol_version.")
        if self.phase is not TrainingPhase.DRILL and self.drill_id is not None:
            raise ValueError("Only drill segments may define drill_id.")
        return self


class DrillEvent(BaseModel):
    """An operator-recorded event within a prescribed drill segment."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    timestamp: datetime
    event_type: str = Field(min_length=1)
    repetition_index: int | None = Field(default=None, ge=1)
    note: str | None = None


class CaptureSession(BaseModel):
    """The single immutable acquisition artifact consumed by Phase 2.

    The capture owns every evidence source needed for a scientific ground-
    truth decision.  The pipeline deliberately does not assemble unrelated
    files after capture has completed.
    """

    model_config = ConfigDict(frozen=True)

    capture_session_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    captured_at: datetime
    raw_feature_vectors: tuple[RawFeatureVector, ...] = Field(min_length=1)
    emg_recordings: tuple[EMGRecording, ...] = Field(min_length=1)
    synchronization_audit: SynchronizationAudit
    drill_events: tuple[DrillEvent, ...] = ()
    placement_records: tuple[SensorPlacementRecord, ...] = Field(min_length=1)
    devices: tuple[DeviceMetadata, ...] = Field(min_length=1)
    calibration_sessions: tuple[CalibrationSession, ...] = Field(min_length=1)
    phases: tuple[TrainingPhaseSegment, ...] = Field(min_length=1)
    source_sha256: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_capture_consistency(self) -> "CaptureSession":
        """Require one player/session and internally consistent capture IDs."""

        vectors = self.raw_feature_vectors
        player_ids = {vector.player.player_id for vector in vectors}
        session_ids = {vector.session.session_id for vector in vectors}
        if len(player_ids) != 1 or len(session_ids) != 1:
            raise ValueError("CaptureSession vectors must belong to one player and session.")

        if len({vector.feature_vector_id for vector in vectors}) != len(vectors):
            raise ValueError("CaptureSession feature_vector_id values must be unique.")
        candidate_keys = {
            (vector.feature_vector_id, group_id)
            for vector in vectors
            for group_id in vector.groups
        }
        audit_keys = {
            (observation.feature_vector_id, observation.group_id)
            for observation in self.synchronization_audit.observations
        }
        if not audit_keys.issubset(candidate_keys):
            raise ValueError("Synchronization audit must not reference an unknown feature vector or group.")
        if len({device.device_id for device in self.devices}) != len(self.devices):
            raise ValueError("CaptureSession device_id values must be unique.")
        if len({record.device_id for record in self.placement_records}) != len(self.placement_records):
            raise ValueError("CaptureSession placement records must be unique per device.")

        device_ids = {device.device_id for device in self.devices}
        for record in self.placement_records:
            if record.device_id not in device_ids:
                raise ValueError("Every placement record must reference a capture device.")
        for recording in self.emg_recordings:
            if recording.device_id not in device_ids:
                raise ValueError("Every EMG recording must reference a capture device.")
        if len({recording.recording_id for recording in self.emg_recordings}) != len(self.emg_recordings):
            raise ValueError("CaptureSession EMG recording IDs must be unique.")
        if len({recording.group_id for recording in self.emg_recordings}) != len(self.emg_recordings):
            raise ValueError("CaptureSession EMG recordings must be unique per group.")
        placements_by_device = {record.device_id: record for record in self.placement_records}
        for recording in self.emg_recordings:
            placement = placements_by_device.get(recording.device_id)
            if placement is not None and placement.group_id != recording.group_id:
                raise ValueError("EMG recording and placement record groups must agree.")

        phase_ids = {phase.segment_id for phase in self.phases}
        if len(phase_ids) != len(self.phases):
            raise ValueError("CaptureSession phase segment IDs must be unique.")
        if any(event.segment_id not in phase_ids for event in self.drill_events):
            raise ValueError("Every drill event must reference a training phase segment.")
        phases_by_id = {phase.segment_id: phase for phase in self.phases}
        for event in self.drill_events:
            phase = phases_by_id[event.segment_id]
            if phase.phase is not TrainingPhase.DRILL:
                raise ValueError("Drill events must reference a drill segment.")
            if not phase.started_at <= event.timestamp <= phase.ended_at:
                raise ValueError("Drill events must occur within their drill segment.")
        ordered_phases = sorted(self.phases, key=lambda phase: phase.started_at)
        if any(
            following.started_at < preceding.ended_at
            for preceding, following in zip(ordered_phases, ordered_phases[1:])
        ):
            raise ValueError("CaptureSession phases must not overlap.")
        return self
