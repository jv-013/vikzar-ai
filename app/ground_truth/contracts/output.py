"""Immutable output contracts for verified synchronized training data."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain_biomarkers import DomainBiomarkers

from .capture import TrainingPhase
from .synchronization import SynchronizationObservation


class WindowDisposition(str, Enum):
    """Ground-truth eligibility outcome for one candidate window."""

    ACCEPTED = "accepted"
    QUESTIONABLE = "questionable"
    REJECTED = "rejected"


class WindowQualityResult(BaseModel):
    """Explainable quality result retained for every evaluated candidate."""

    model_config = ConfigDict(frozen=True)

    feature_vector_id: str
    group_id: str
    disposition: WindowDisposition
    reasons: tuple[str, ...] = ()


class AlignedTrainingWindow(BaseModel):
    """One measured Smart Pod and EMG window with capture synchronization evidence."""

    model_config = ConfigDict(frozen=True)

    aligned_window_id: str
    source_feature_vector_id: str
    group_id: str
    window_start_ms: float
    window_end_ms: float
    phase_segment_id: str
    phase: TrainingPhase
    drill_id: str | None = None
    drill_protocol_version: str | None = None
    smart_pod_features: dict[str, DomainBiomarkers]
    emg_measurements: DomainBiomarkers
    synchronization: SynchronizationObservation


class MeasuredEMGLabel(BaseModel):
    """A measured EMG target derived without prediction or imputation."""

    model_config = ConfigDict(frozen=True)

    aligned_window_id: str
    group_id: str
    metric_name: str
    value: float
    amplitude_unit: str
    normalization_method: str
    source_feature_vector_id: str


class SessionQualityReport(BaseModel):
    """Session quality outcomes and all exclusion reasons."""

    model_config = ConfigDict(frozen=True)

    evaluated_at: datetime
    total_candidates: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    questionable_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    results: tuple[WindowQualityResult, ...]


class ProvenanceRecord(BaseModel):
    """Reproducibility evidence for a verified ground-truth output."""

    model_config = ConfigDict(frozen=True)

    ground_truth_schema_version: str
    capture_session_schema_version: str
    capture_session_id: str
    generated_at: datetime
    source_sha256: dict[str, str]
    synchronization_audit_id: str


class VerifiedSynchronizedTrainingSession(BaseModel):
    """The immutable Phase 2 output consumed by the future dataset builder."""

    model_config = ConfigDict(frozen=True)

    verified_session_id: str
    capture_session_id: str
    player_id: str
    session_id: str
    aligned_windows: tuple[AlignedTrainingWindow, ...]
    labels: tuple[MeasuredEMGLabel, ...]
    quality_report: SessionQualityReport
    provenance: ProvenanceRecord
