"""Frozen-phase pipeline orchestration and optional synchronization."""

from __future__ import annotations

import time

from starlette.concurrency import run_in_threadpool

from app.inference.contracts import InferenceRequest
from app.risk_engine.contracts import RiskAssessmentRequest
from app.validation import validate_raw_feature_vector

from .configuration import APISettings
from .contracts import (
    CorrelationResponse,
    PipelineRequestEnvelope,
    PipelineResponse,
    SessionSnapshot,
    SessionStartRequest,
    SynchronizationResult,
)
from .dependencies import BaselineRepository, InferenceGateway, RiskGateway
from .exceptions import PipelineOrchestrationError, SessionConflictError
from .firebase import FirebaseSynchronizer
from .metrics import MetricsRegistry
from .session import SessionManager


class PipelineOrchestrator:
    """Wire validation to Phase 8 to Phase 9 without bypass or recomputation."""

    def __init__(
        self,
        *,
        settings: APISettings,
        inference_engine: InferenceGateway,
        risk_engine: RiskGateway,
        baselines: BaselineRepository,
        sessions: SessionManager,
        firebase: FirebaseSynchronizer,
        metrics: MetricsRegistry,
    ) -> None:
        self._settings = settings
        self._inference = inference_engine
        self._risk = risk_engine
        self._baselines = baselines
        self._sessions = sessions
        self._firebase = firebase
        self._metrics = metrics

    async def start_session(
        self,
        request: SessionStartRequest,
        *,
        correlation_id: str,
    ) -> CorrelationResponse:
        snapshot = self._sessions.start(request)
        sync = await self._firebase.sync_session(snapshot)
        return CorrelationResponse(
            correlation_id=correlation_id,
            session=snapshot,
            synchronization=sync,
        )

    async def session_transition(
        self,
        snapshot: SessionSnapshot,
        *,
        correlation_id: str,
    ) -> CorrelationResponse:
        sync = await self._firebase.sync_session(snapshot)
        return CorrelationResponse(
            correlation_id=correlation_id,
            session=snapshot,
            synchronization=sync,
        )

    async def process(
        self,
        session_id: str,
        request: PipelineRequestEnvelope,
    ) -> PipelineResponse:
        started = time.perf_counter()
        try:
            local = await run_in_threadpool(
                self._process_local,
                session_id,
                request,
            )
        except Exception:
            self._metrics.record_pipeline(
                latency_ms=(time.perf_counter() - started) * 1000,
                failed=True,
            )
            raise
        snapshot, predictions, assessment, drill = local
        sync = await self._firebase.sync_assessment(
            assessment,
            current_drill=drill,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        self._metrics.record_pipeline(latency_ms=latency_ms, failed=False)
        return PipelineResponse(
            session=snapshot,
            predictions=predictions,
            risk_assessment=assessment,
            synchronization=sync,
            processing_ms=latency_ms,
        )

    def _process_local(
        self,
        session_id: str,
        request: PipelineRequestEnvelope,
    ) -> tuple[SessionSnapshot, tuple, object, str | None]:
        with self._sessions.processing(session_id):
            checkpoint = self._sessions.metadata(session_id)
            if checkpoint.snapshot.state.value != "active":
                raise SessionConflictError("Session must be active for processing.")
            vector = validate_raw_feature_vector(request.feature_vector)
            if vector.session.session_id != session_id:
                raise PipelineOrchestrationError(
                    "Feature vector session does not match the API session."
                )
            if vector.player.model_dump() != checkpoint.player.model_dump():
                raise PipelineOrchestrationError(
                    "Feature vector player metadata does not match session start."
                )
            baseline = self._baselines.get(vector.player.player_id)
            if baseline is None:
                raise PipelineOrchestrationError(
                    "No approved local player risk baseline is available."
                )
            group_ids = (
                self._settings.left_group_id,
                self._settings.right_group_id,
            )
            if any(group_id not in vector.groups for group_id in group_ids):
                raise PipelineOrchestrationError(
                    "Validated feature vector lacks the configured bilateral groups."
                )
            inference_requests = tuple(
                InferenceRequest(feature_vector=vector, group_id=group_id)
                for group_id in group_ids
            )
            predictions = self._inference.predict_batch(inference_requests)
            history = self._sessions.history(session_id) + predictions
            assessment = self._risk.assess(
                RiskAssessmentRequest.from_runtime(
                    predictions=history,
                    player=vector.player,
                    session=vector.session,
                    baseline=baseline,
                )
            )
            snapshot = self._sessions.append_predictions(
                session_id,
                predictions,
            )
            return snapshot, predictions, assessment, vector.session.drill

    async def shutdown(self) -> tuple[SessionSnapshot, ...]:
        snapshots = self._sessions.shutdown()
        for snapshot in snapshots:
            await self._firebase.sync_session(snapshot)
        await self._firebase.close()
        return snapshots
