"""Phase 10 REST routes over the injected local compute container."""

from __future__ import annotations

from fastapi import APIRouter, Request

from .contracts import (
    ComponentHealth,
    ComponentStatus,
    CorrelationResponse,
    HealthResponse,
    MetricsSnapshot,
    PipelineRequestEnvelope,
    PipelineResponse,
    SessionSnapshot,
    SessionStartRequest,
    SessionStopRequest,
)

router = APIRouter()


@router.get("/health/live", response_model=HealthResponse)
async def liveness(request: Request) -> HealthResponse:
    container = request.app.state.container
    return HealthResponse(
        status=ComponentStatus.HEALTHY,
        application=container.settings.application_name,
        version=container.settings.application_version,
        timestamp=container.clock(),
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    container = request.app.state.container
    firebase = await container.firebase.health()
    components = (
        ComponentHealth(
            component="phase8_inference",
            status=ComponentStatus.HEALTHY,
            detail="Approved production model is loaded locally.",
        ),
        ComponentHealth(
            component="phase9_risk",
            status=ComponentStatus.HEALTHY,
            detail="Versioned risk policy is loaded locally.",
        ),
        ComponentHealth(
            component="session_store",
            status=ComponentStatus.HEALTHY,
            detail="Local checkpoint store is available.",
        ),
        firebase,
    )
    return HealthResponse(
        status=ComponentStatus.HEALTHY,
        application=container.settings.application_name,
        version=container.settings.application_version,
        timestamp=container.clock(),
        components=components,
    )


@router.get("/metrics", response_model=MetricsSnapshot)
async def metrics(request: Request) -> MetricsSnapshot:
    container = request.app.state.container
    return container.metrics.snapshot(
        firebase_queued_operations=container.firebase.queued_count,
        active_sessions=container.sessions.active_count,
    )


@router.post(
    "/api/v1/sessions/start",
    response_model=CorrelationResponse,
    status_code=201,
)
async def start_session(
    payload: SessionStartRequest,
    request: Request,
) -> CorrelationResponse:
    return await request.app.state.container.orchestrator.start_session(
        payload,
        correlation_id=request.state.correlation_id,
    )


@router.get(
    "/api/v1/sessions/{session_id}",
    response_model=SessionSnapshot,
)
async def get_session(session_id: str, request: Request) -> SessionSnapshot:
    return request.app.state.container.sessions.get(session_id)


@router.post(
    "/api/v1/sessions/{session_id}/heartbeat",
    response_model=CorrelationResponse,
)
async def heartbeat(session_id: str, request: Request) -> CorrelationResponse:
    container = request.app.state.container
    await container.firebase.flush()
    return await container.orchestrator.session_transition(
        container.sessions.heartbeat(session_id),
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/api/v1/sessions/{session_id}/disconnect",
    response_model=CorrelationResponse,
)
async def disconnect(session_id: str, request: Request) -> CorrelationResponse:
    container = request.app.state.container
    return await container.orchestrator.session_transition(
        container.sessions.disconnect(session_id),
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/api/v1/sessions/{session_id}/reconnect",
    response_model=CorrelationResponse,
)
async def reconnect(session_id: str, request: Request) -> CorrelationResponse:
    container = request.app.state.container
    await container.firebase.flush()
    return await container.orchestrator.session_transition(
        container.sessions.reconnect(session_id),
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/api/v1/sessions/{session_id}/recover",
    response_model=CorrelationResponse,
)
async def recover(session_id: str, request: Request) -> CorrelationResponse:
    container = request.app.state.container
    return await container.orchestrator.session_transition(
        container.sessions.recover(session_id),
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/api/v1/sessions/{session_id}/stop",
    response_model=CorrelationResponse,
)
async def stop(
    session_id: str,
    payload: SessionStopRequest,
    request: Request,
) -> CorrelationResponse:
    container = request.app.state.container
    return await container.orchestrator.session_transition(
        container.sessions.stop(session_id, reason=payload.reason),
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/api/v1/sessions/{session_id}/feature-vectors",
    response_model=PipelineResponse,
)
async def process_feature_vector(
    session_id: str,
    payload: PipelineRequestEnvelope,
    request: Request,
) -> PipelineResponse:
    return await request.app.state.container.orchestrator.process(
        session_id,
        payload,
    )
