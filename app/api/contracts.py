"""Immutable Phase 10 API, lifecycle, health, and response contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.inference.contracts import InferencePrediction
from app.risk_engine.contracts import RiskAssessment
from app.schemas.player import Player
from app.schemas.raw_feature_vector import RawFeatureVector
from app.schemas.session import Session

_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


class SessionLifecycleState(str, Enum):
    """Deterministic local session states."""

    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    STOPPED = "stopped"


class SyncStatus(str, Enum):
    """Optional Firebase delivery outcome."""

    DISABLED = "disabled"
    SYNCHRONIZED = "synchronized"
    QUEUED = "queued"
    DEFERRED = "deferred"


class ComponentStatus(str, Enum):
    """Health state for one local or optional component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class SessionStartRequest(BaseModel):
    """Existing player/session metadata required to start local computation."""

    model_config = ConfigDict(frozen=True)

    player: Player
    session: Session

    @model_validator(mode="after")
    def validate_identifiers(self) -> "SessionStartRequest":
        import re

        if not re.fullmatch(_SAFE_ID, self.player.player_id) or not re.fullmatch(
            _SAFE_ID,
            self.session.session_id,
        ):
            raise ValueError("Player and session identifiers are unsafe.")
        return self


class SessionStopRequest(BaseModel):
    """Optional operational reason retained with a stopped session."""

    model_config = ConfigDict(frozen=True)

    reason: str = Field(default="requested", min_length=1, max_length=256)


class SessionSnapshot(BaseModel):
    """Immutable public lifecycle snapshot without local prediction history."""

    model_config = ConfigDict(frozen=True)

    session_id: str = Field(pattern=_SAFE_ID)
    player_id: str = Field(pattern=_SAFE_ID)
    state: SessionLifecycleState
    started_at: datetime
    last_heartbeat_at: datetime
    ended_at: datetime | None = None
    stop_reason: str | None = None
    prediction_count: int = Field(ge=0)
    recovery_count: int = Field(ge=0)


class SessionCheckpoint(BaseModel):
    """Local-only recoverable session state; never synchronized to Firebase."""

    model_config = ConfigDict(frozen=True)

    snapshot: SessionSnapshot
    player: Player
    session: Session
    predictions: tuple[InferencePrediction, ...] = ()


class SynchronizationResult(BaseModel):
    """Cloud synchronization status without exposing transport details."""

    model_config = ConfigDict(frozen=True)

    status: SyncStatus
    operation_id: str | None = None
    queued_operations: int = Field(ge=0)


class PipelineResponse(BaseModel):
    """Local Phase 8/9 output plus optional allowlisted synchronization status."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    session: SessionSnapshot
    predictions: tuple[InferencePrediction, ...] = Field(min_length=2)
    risk_assessment: RiskAssessment
    synchronization: SynchronizationResult
    processing_ms: float = Field(ge=0)


class ComponentHealth(BaseModel):
    """One named startup/runtime health observation."""

    model_config = ConfigDict(frozen=True)

    component: str = Field(min_length=1)
    status: ComponentStatus
    detail: str = Field(min_length=1)


class HealthResponse(BaseModel):
    """Liveness/readiness response."""

    model_config = ConfigDict(frozen=True)

    status: ComponentStatus
    application: str = Field(min_length=1)
    version: str = Field(min_length=1)
    timestamp: datetime
    components: tuple[ComponentHealth, ...] = ()


class MetricsSnapshot(BaseModel):
    """Process-local counters and latency aggregates."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    requests_total: int = Field(ge=0)
    requests_failed: int = Field(ge=0)
    pipeline_requests: int = Field(ge=0)
    pipeline_failures: int = Field(ge=0)
    pipeline_latency_ms_total: float = Field(ge=0)
    firebase_queued_operations: int = Field(ge=0)
    active_sessions: int = Field(ge=0)


class APIErrorDetail(BaseModel):
    """Stable, non-secret error payload."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    timestamp: datetime
    details: tuple[str, ...] = ()


class APIErrorResponse(BaseModel):
    """Standard exception envelope."""

    model_config = ConfigDict(frozen=True)

    error: APIErrorDetail


class CorrelationResponse(BaseModel):
    """Lifecycle result paired with request tracing identity."""

    model_config = ConfigDict(frozen=True)

    correlation_id: str = Field(min_length=1)
    session: SessionSnapshot
    synchronization: SynchronizationResult


class PipelineRequestEnvelope(BaseModel):
    """Explicit feature-input wrapper reserved for the completed ETL output."""

    model_config = ConfigDict(frozen=True)

    feature_vector: RawFeatureVector
