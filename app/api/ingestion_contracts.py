"""Payloads for the five HTTPS Callable Cloud Functions defined by the
Flutter application's BACKEND_SPECIFICATION.md §17/§21 — the exact,
binding contract between this pipeline (the "laptop") and Firebase.

These mirror `vikzar-app/functions/src/contracts/types.ts` field-for-field
by design: the two repositories must agree on this boundary without
either depending on the other's source, per the platform's separate-repos
architecture (DECISIONS.md, cross-repo contract alignment ADR).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StartSessionPayload(BaseModel):
    """§21.3."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    player_id: str
    team_id: str | None = None
    org_id: str | None = None
    type: str
    device_ids: tuple[str, ...]
    started_at: datetime

    def to_wire(self) -> dict[str, Any]:
        return _drop_none(
            {
                "sessionId": self.session_id,
                "playerId": self.player_id,
                "teamId": self.team_id,
                "orgId": self.org_id,
                "type": self.type,
                "deviceIds": list(self.device_ids),
                "startedAt": self.started_at.isoformat(),
            }
        )


class LiveTickMetrics(BaseModel):
    """§21.4's `metrics` map, plus the additive risk-engine sub-scores
    (DECISIONS.md cross-repo contract alignment ADR)."""

    model_config = ConfigDict(frozen=True)

    current_load: float
    cumulative_impacts: int
    risk_score: float
    risk_level: str
    emg_activation: float | None = None
    confidence: float | None = None
    fatigue_score: float | None = None
    fatigue_level: str | None = None
    workload_ratio: float | None = None
    workload_status: str | None = None
    asymmetry_score: float | None = None
    asymmetry_status: str | None = None
    muscle_balance_score: float | None = None
    muscle_balance_status: str | None = None

    def to_wire(self) -> dict[str, Any]:
        return _drop_none(
            {
                "currentLoad": self.current_load,
                "cumulativeImpacts": self.cumulative_impacts,
                "riskScore": self.risk_score,
                "riskLevel": self.risk_level,
                "emgActivation": self.emg_activation,
                "confidence": self.confidence,
                "fatigueScore": self.fatigue_score,
                "fatigueLevel": self.fatigue_level,
                "workloadRatio": self.workload_ratio,
                "workloadStatus": self.workload_status,
                "asymmetryScore": self.asymmetry_score,
                "asymmetryStatus": self.asymmetry_status,
                "muscleBalanceScore": self.muscle_balance_score,
                "muscleBalanceStatus": self.muscle_balance_status,
            }
        )


class IngestLiveTickPayload(BaseModel):
    """§21.4."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    player_id: str
    team_id: str | None = None
    sequence_number: int
    tick_timestamp: datetime
    connection_status: str
    metrics: LiveTickMetrics
    device_battery: dict[str, float] | None = None

    def to_wire(self) -> dict[str, Any]:
        return _drop_none(
            {
                "sessionId": self.session_id,
                "playerId": self.player_id,
                "teamId": self.team_id,
                "sequenceNumber": self.sequence_number,
                "tickTimestamp": self.tick_timestamp.isoformat(),
                "connectionStatus": self.connection_status,
                "metrics": self.metrics.to_wire(),
                "deviceBattery": self.device_battery,
            }
        )


class SummaryMetricsPayload(BaseModel):
    """§9 / §21.5."""

    model_config = ConfigDict(frozen=True)

    total_impacts: int
    peak_impact_force: float
    average_load: float
    cumulative_load_index: float
    muscle_fatigue_index: float | None = None
    overall_risk_score: float
    risk_level: str
    risk_factors: tuple[str, ...] = ()

    def to_wire(self) -> dict[str, Any]:
        return _drop_none(
            {
                "totalImpacts": self.total_impacts,
                "peakImpactForce": self.peak_impact_force,
                "averageLoad": self.average_load,
                "cumulativeLoadIndex": self.cumulative_load_index,
                "muscleFatigueIndex": self.muscle_fatigue_index,
                "overallRiskScore": self.overall_risk_score,
                "riskLevel": self.risk_level,
                "riskFactors": list(self.risk_factors),
            }
        )


class CompleteSessionPayload(BaseModel):
    """§21.5."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    ended_at: datetime
    duration_seconds: int
    status: str
    summary_metrics: SummaryMetricsPayload
    data_completeness: float
    pipeline_version: str
    raw_data_storage_path: str | None = None

    def to_wire(self) -> dict[str, Any]:
        return _drop_none(
            {
                "sessionId": self.session_id,
                "endedAt": self.ended_at.isoformat(),
                "durationSeconds": self.duration_seconds,
                "status": self.status,
                "summaryMetrics": self.summary_metrics.to_wire(),
                "dataCompleteness": self.data_completeness,
                "pipelineVersion": self.pipeline_version,
                "rawDataStoragePath": self.raw_data_storage_path,
            }
        )


class ContributingFactorPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    component: str
    score: float
    weight: float
    contribution: float

    def to_wire(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "score": self.score,
            "weight": self.weight,
            "contribution": self.contribution,
        }


class RecommendationPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    priority: str
    message: str

    def to_wire(self) -> dict[str, Any]:
        return {"code": self.code, "priority": self.priority, "message": self.message}


class SubmitAlertPayload(BaseModel):
    """§21.6, plus the additive risk-engine provenance fields (DECISIONS.md
    cross-repo contract alignment ADR)."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    player_id: str
    team_id: str | None = None
    severity: str
    type: str
    message: str
    triggered_at: datetime
    metrics_snapshot: dict[str, Any] | None = None
    contributing_factors: tuple[ContributingFactorPayload, ...] = ()
    recommendations: tuple[RecommendationPayload, ...] = ()
    confidence: float | None = None
    policy_version: str | None = None
    model_version: str | None = None
    assessment_id: str | None = None
    assessment_checksum: str | None = None

    def to_wire(self) -> dict[str, Any]:
        return _drop_none(
            {
                "sessionId": self.session_id,
                "playerId": self.player_id,
                "teamId": self.team_id,
                "severity": self.severity,
                "type": self.type,
                "message": self.message,
                "triggeredAt": self.triggered_at.isoformat(),
                "metricsSnapshot": self.metrics_snapshot,
                "contributingFactors": [f.to_wire() for f in self.contributing_factors] or None,
                "recommendations": [r.to_wire() for r in self.recommendations] or None,
                "confidence": self.confidence,
                "policyVersion": self.policy_version,
                "modelVersion": self.model_version,
                "assessmentId": self.assessment_id,
                "assessmentChecksum": self.assessment_checksum,
            }
        )


class SubmitReportPayload(BaseModel):
    """§21.7."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    player_id: str
    team_id: str | None = None
    generated_at: datetime
    summary: dict[str, Any]
    storage_path: str | None = None

    def to_wire(self) -> dict[str, Any]:
        return _drop_none(
            {
                "sessionId": self.session_id,
                "playerId": self.player_id,
                "teamId": self.team_id,
                "generatedAt": self.generated_at.isoformat(),
                "summary": self.summary,
                "storagePath": self.storage_path,
            }
        )


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    """Omits `None`-valued keys — the Cloud Functions treat an absent
    optional field and an explicit `null` differently only for `teamId`/
    `orgId` scope checks (BACKEND_SPECIFICATION.md §0/§3), so this keeps
    the wire payload matching §21's own examples, which never include a
    null-valued key."""
    return {key: value for key, value in payload.items() if value is not None}
