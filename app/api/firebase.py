"""Optional Firebase synchronization for the local compute node — calls
the Flutter application's HTTPS Callable Cloud Functions
(BACKEND_SPECIFICATION.md §17/§21) rather than writing to Firestore
directly.

**Revised — cross-repo contract alignment (DECISIONS.md ADR).** Earlier,
this module wrote directly to ad-hoc Firestore paths (`live/`, `players/`,
`reports/`, `analytics/`) via a generic `FirebaseTransport.write(updates)`
call. That never matched `vikzar-app`'s actual schema and, more
importantly, contradicted its own documented trust boundary: the laptop
pipeline is explicitly forbidden from holding direct Firestore write
access (BACKEND_SPECIFICATION.md §0) — it authenticates as a scoped
"ingestion principal" and calls a small, fixed set of Cloud Functions
instead. Since no concrete `FirebaseTransport` was ever built or
committed, this is a pre-launch correction, not a rewrite of working code.
`FirebaseTransport` now exposes one method per Cloud Function; this class's
allowlist/queue/retry resilience is unchanged in spirit, restructured to
queue typed calls instead of raw path/value writes.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

from app.risk_engine.contracts import AlertSeverity, RiskAssessment, TriggeredAlert

from .contracts import (
    ComponentHealth,
    ComponentStatus,
    SessionSnapshot,
    SyncStatus,
    SynchronizationResult,
)
from .ingestion_contracts import (
    ContributingFactorPayload,
    IngestLiveTickPayload,
    LiveTickMetrics,
    RecommendationPayload,
    SubmitAlertPayload,
)

logger = logging.getLogger(__name__)


class FirebaseTransport(Protocol):
    """Deployment adapter — one method per HTTPS Callable Cloud Function
    this pipeline is authorized to call (BACKEND_SPECIFICATION.md §21).
    A concrete implementation (`firebase_callable_transport.py`) invokes
    the deployed function over HTTPS, authenticated as the ingestion
    principal; the allowlist/forbidden-key discipline the old generic
    `write()` enforced is now structural — these methods only ever accept
    the typed payloads in `ingestion_contracts.py`, which have no raw
    sensor or feature-vector fields to begin with."""

    async def call_ingest_live_tick(self, payload: IngestLiveTickPayload) -> None: ...

    async def call_submit_alert(self, payload: SubmitAlertPayload) -> None: ...

    async def health(self) -> bool:
        """Return transport availability without performing compute."""

    async def close(self) -> None:
        """Release provider resources."""


@dataclass(frozen=True)
class _QueuedCall:
    operation_id: str
    method_name: str
    payload: IngestLiveTickPayload | SubmitAlertPayload


# vikzar-ai's own AlertSeverity has 4 values (info/warning/high/critical);
# BACKEND_SPECIFICATION.md's alerts.severity has 3 (info/warning/critical).
# HIGH maps to "warning", not "critical" — "critical" stays reserved for
# vikzar-ai's own CRITICAL, matching the Flutter app's rule that Alert
# Crimson (the UI treatment tied to severity "critical") is scoped
# exclusively to genuinely critical states, never inflated.
_SEVERITY_MAP: dict[AlertSeverity, str] = {
    AlertSeverity.INFO: "info",
    AlertSeverity.WARNING: "warning",
    AlertSeverity.HIGH: "warning",
    AlertSeverity.CRITICAL: "critical",
}


class FirebaseSynchronizer:
    """Project computed summaries only; never upload feature vectors or run AI."""

    def __init__(
        self,
        transport: FirebaseTransport | None,
        *,
        enabled: bool,
        queue_capacity: int,
    ) -> None:
        self._transport = transport
        self._enabled = enabled
        self._capacity = queue_capacity
        self._queue: OrderedDict[str, _QueuedCall] = OrderedDict()

    @property
    def queued_count(self) -> int:
        return len(self._queue)

    async def sync_session(self, snapshot: SessionSnapshot) -> SynchronizationResult:
        """**Known gap, not silently worked around**: `startSession`/
        `completeSession` (BACKEND_SPECIFICATION.md §21.3/§21.5) require
        `type` (training/match) and `deviceIds`, neither of which exist
        anywhere in this pipeline's `SessionStartRequest`/`Session` schema
        (`app/schemas/session.py`) today. Rather than fabricate those
        fields, this reports `SyncStatus.DISABLED` honestly — session
        lifecycle sync is not yet wired to a real Cloud Function call.
        Closing this gap requires extending `Session`/`SessionStartRequest`
        with the missing fields first, a schema decision out of scope for
        a transport-layer change (see DECISIONS.md)."""
        del snapshot
        return SynchronizationResult(status=SyncStatus.DISABLED, queued_operations=len(self._queue))

    async def sync_assessment(
        self,
        assessment: RiskAssessment,
        *,
        current_drill: str | None,
    ) -> SynchronizationResult:
        del current_drill  # not part of the §21.4 ingestLiveTick contract
        tick_payload = self._build_live_tick_payload(assessment)
        result = await self._deliver("call_ingest_live_tick", tick_payload)

        for alert in assessment.alerts:
            alert_payload = self._build_alert_payload(assessment, alert)
            # Best-effort: an alert delivery failure does not override an
            # otherwise-successful tick delivery's reported status.
            await self._deliver("call_submit_alert", alert_payload)

        return result

    def _build_live_tick_payload(self, assessment: RiskAssessment) -> IngestLiveTickPayload:
        provenance = assessment.provenance
        metrics = LiveTickMetrics(
            current_load=assessment.workload.current_load,
            # **Known gap, not fabricated**: vikzar-ai has no impact-event
            # concept anywhere in its ETL/feature/model output today (no
            # `app/etl/feature_extraction` module produces one). `0` here
            # is an explicit, documented placeholder — not a claim that
            # zero impacts occurred — until impact detection exists
            # somewhere upstream. See DECISIONS.md / the platform-lock
            # report for this as a named, tracked gap.
            cumulative_impacts=0,
            # RiskAssessment.risk_score is 0-100 (RiskComponent scale);
            # BACKEND_SPECIFICATION.md §21.4's riskScore is 0.0-1.0.
            risk_score=assessment.risk_score / 100.0,
            risk_level=assessment.risk_level.value,
            confidence=assessment.confidence,
            fatigue_score=assessment.fatigue.score,
            fatigue_level=assessment.fatigue.level.value,
            workload_ratio=assessment.workload.workload_ratio,
            workload_status=assessment.workload.status.value,
            asymmetry_score=assessment.asymmetry.score,
            asymmetry_status=assessment.asymmetry.status.value,
            muscle_balance_score=assessment.muscle_balance.score,
            muscle_balance_status=assessment.muscle_balance.status.value,
        )
        return IngestLiveTickPayload(
            session_id=provenance.session_id,
            player_id=provenance.player_id,
            # team_id: vikzar-ai has no team concept anywhere in its
            # schemas today — always omitted, not fabricated.
            sequence_number=len(provenance.prediction_ids),
            tick_timestamp=provenance.assessed_at,
            connection_status="connected",
            metrics=metrics,
        )

    def _build_alert_payload(
        self, assessment: RiskAssessment, alert: TriggeredAlert
    ) -> SubmitAlertPayload:
        provenance = assessment.provenance
        return SubmitAlertPayload(
            session_id=provenance.session_id,
            player_id=provenance.player_id,
            severity=_SEVERITY_MAP[alert.severity],
            # BACKEND_SPECIFICATION.md §1.10's `type` enum is a fixed,
            # narrow vocabulary (high_impact/risk_threshold_exceeded/
            # abnormal_fatigue_asymmetry/device_disconnected/low_battery)
            # that predates and does not match vikzar-ai's free-form
            # `TriggeredAlert.code`. Every risk-engine-raised alert maps
            # to "risk_threshold_exceeded" — the one type §21.6's own
            # docstring names for this exact origin ("whenever the Risk
            # Engine crosses a threshold") — rather than guessing a more
            # specific type from an unstructured code string.
            type="risk_threshold_exceeded",
            message=alert.message,
            triggered_at=provenance.assessed_at,
            confidence=assessment.confidence,
            policy_version=provenance.policy_version,
            model_version=provenance.model_version,
            assessment_id=assessment.assessment_id,
            contributing_factors=tuple(
                ContributingFactorPayload(
                    component=factor.component.value,
                    score=factor.component_score,
                    weight=factor.weight,
                    contribution=factor.weighted_contribution,
                )
                for factor in assessment.contributing_factors
            ),
            recommendations=tuple(
                RecommendationPayload(
                    code=recommendation.code,
                    priority=recommendation.priority.value,
                    message=recommendation.message,
                )
                for recommendation in assessment.recommendations
            ),
        )

    async def flush(self) -> int:
        if not self._enabled or self._transport is None:
            return 0
        delivered = 0
        for operation_id in tuple(self._queue):
            call = self._queue[operation_id]
            try:
                await self._invoke(call.method_name, call.payload)
            except Exception:
                break
            del self._queue[operation_id]
            delivered += 1
        return delivered

    async def health(self) -> ComponentHealth:
        if not self._enabled:
            return ComponentHealth(
                component="firebase",
                status=ComponentStatus.DISABLED,
                detail="Optional Firebase synchronization is disabled.",
            )
        if self._transport is None:
            return ComponentHealth(
                component="firebase",
                status=ComponentStatus.UNAVAILABLE,
                detail="Firebase transport hook is not configured.",
            )
        try:
            available = await self._transport.health()
        except Exception:
            available = False
        return ComponentHealth(
            component="firebase",
            status=(
                ComponentStatus.HEALTHY
                if available and not self._queue
                else ComponentStatus.DEGRADED
            ),
            detail=(
                "Firebase synchronization is available."
                if available and not self._queue
                else f"Firebase has {len(self._queue)} deferred operation(s)."
            ),
        )

    async def close(self) -> None:
        if self._transport is not None:
            await self.flush()
            await self._transport.close()

    async def _deliver(
        self,
        method_name: str,
        payload: IngestLiveTickPayload | SubmitAlertPayload,
    ) -> SynchronizationResult:
        if not self._enabled:
            return SynchronizationResult(status=SyncStatus.DISABLED, queued_operations=0)

        operation_id = self._operation_id(method_name, payload)
        if self._transport is not None:
            try:
                await self._invoke(method_name, payload)
                return SynchronizationResult(
                    status=SyncStatus.SYNCHRONIZED,
                    operation_id=operation_id,
                    queued_operations=len(self._queue),
                )
            except Exception:
                logger.warning("Firebase call %s failed; queuing for retry.", method_name)

        if operation_id not in self._queue and len(self._queue) < self._capacity:
            self._queue[operation_id] = _QueuedCall(
                operation_id=operation_id,
                method_name=method_name,
                payload=payload,
            )
            status = SyncStatus.QUEUED
        elif operation_id in self._queue:
            status = SyncStatus.QUEUED
        else:
            status = SyncStatus.DEFERRED
        return SynchronizationResult(
            status=status,
            operation_id=operation_id,
            queued_operations=len(self._queue),
        )

    async def _invoke(
        self,
        method_name: str,
        payload: IngestLiveTickPayload | SubmitAlertPayload,
    ) -> None:
        assert self._transport is not None
        method = getattr(self._transport, method_name)
        await method(payload)

    @staticmethod
    def _operation_id(
        method_name: str,
        payload: IngestLiveTickPayload | SubmitAlertPayload,
    ) -> str:
        encoded = json.dumps(
            {"method": method_name, "payload": payload.model_dump(mode="json")},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"firebase-operation-{hashlib.sha256(encoded).hexdigest()[:24]}"
