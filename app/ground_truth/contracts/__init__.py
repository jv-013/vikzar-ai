"""Immutable contracts for captured and verified training-session data."""

from .capture import (
    CalibrationSession,
    CaptureSession,
    DeviceMetadata,
    DrillEvent,
    EMGRecording,
    SensorPlacementRecord,
    TrainingPhase,
    TrainingPhaseSegment,
)
from .output import (
    AlignedTrainingWindow,
    MeasuredEMGLabel,
    ProvenanceRecord,
    SessionQualityReport,
    VerifiedSynchronizedTrainingSession,
    WindowDisposition,
    WindowQualityResult,
)
from .synchronization import (
    SynchronizationAudit,
    SynchronizationObservation,
    SynchronizationStatus,
)

__all__ = [
    "AlignedTrainingWindow",
    "CalibrationSession",
    "CaptureSession",
    "DeviceMetadata",
    "DrillEvent",
    "EMGRecording",
    "MeasuredEMGLabel",
    "ProvenanceRecord",
    "SensorPlacementRecord",
    "SessionQualityReport",
    "SynchronizationAudit",
    "SynchronizationObservation",
    "SynchronizationStatus",
    "TrainingPhase",
    "TrainingPhaseSegment",
    "VerifiedSynchronizedTrainingSession",
    "WindowDisposition",
    "WindowQualityResult",
]
