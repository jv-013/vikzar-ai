"""FastAPI bootstrap, production assembly, startup validation, and shutdown."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.experiments.artifact_store import ExperimentArtifactStore
from app.inference import ApprovedModelReferences, InferenceEngine
from app.inference.exceptions import InferenceError
from app.risk_engine import ACLRiskEngine, RiskEngineConfig
from app.risk_engine.exceptions import RiskEngineError
from app.validation.exceptions import ValidationError as FeatureValidationError

from .auth import AnonymousAuthenticator, Authenticator
from .configuration import APISettings
from .dependencies import (
    ApplicationDependencies,
    InMemoryBaselineRepository,
)
from .exceptions import (
    APIConfigurationError,
    PipelineOrchestrationError,
    SessionConflictError,
    SessionNotFoundError,
    SessionRecoveryError,
)
from .firebase import FirebaseSynchronizer, FirebaseTransport
from .firebase_callable_transport import (
    FirebaseCallableTransport,
    FirebaseCallableTransportConfig,
)
from .logging import configure_structured_logging
from .metrics import MetricsRegistry
from .middleware import (
    AuthenticationMiddleware,
    CorrelationMiddleware,
    RequestBodyLimitMiddleware,
    RequestObservabilityMiddleware,
    error_response,
)
from .orchestration import PipelineOrchestrator
from .routes import router
from .session import LocalSessionCheckpointStore, SessionManager


@dataclass(frozen=True)
class RuntimeContainer:
    """Fully assembled local compute application state."""

    settings: APISettings
    clock: Callable[[], datetime]
    sessions: SessionManager
    firebase: FirebaseSynchronizer
    metrics: MetricsRegistry
    orchestrator: PipelineOrchestrator


def create_app(dependencies: ApplicationDependencies) -> FastAPI:
    """Build a production application from explicit injected dependencies."""

    settings = dependencies.settings
    if settings.auth_required and dependencies.authenticator is None:
        raise APIConfigurationError(
            "Authentication is required but no provider hook was injected."
        )
    if settings.firebase_enabled and dependencies.firebase_transport is None:
        raise APIConfigurationError(
            "Firebase is enabled but no synchronization transport was injected."
        )
    authenticator = dependencies.authenticator or AnonymousAuthenticator()
    metrics = MetricsRegistry()
    sessions = SessionManager(
        dependencies.checkpoint_store,
        heartbeat_timeout_seconds=settings.heartbeat_timeout_seconds,
        clock=dependencies.clock,
    )
    firebase = FirebaseSynchronizer(
        dependencies.firebase_transport,
        enabled=settings.firebase_enabled,
        queue_capacity=settings.firebase_queue_capacity,
    )
    orchestrator = PipelineOrchestrator(
        settings=settings,
        inference_engine=dependencies.inference_engine,
        risk_engine=dependencies.risk_engine,
        baselines=dependencies.baseline_repository,
        sessions=sessions,
        firebase=firebase,
        metrics=metrics,
    )
    container = RuntimeContainer(
        settings=settings,
        clock=dependencies.clock,
        sessions=sessions,
        firebase=firebase,
        metrics=metrics,
        orchestrator=orchestrator,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_structured_logging(settings.log_level)
        logger = logging.getLogger("app.api")
        logger.info(
            "application.started",
            extra={"event": "application.started"},
        )
        yield
        stopped = await orchestrator.shutdown()
        logger.info(
            "application.stopped",
            extra={
                "event": "application.stopped",
                "status_code": len(stopped),
            },
        )

    app = FastAPI(
        title=settings.application_name,
        version=settings.application_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.state.container = container
    app.include_router(router)
    _install_exception_handlers(app, dependencies.clock)
    app.add_middleware(
        RequestObservabilityMiddleware,
        metrics=metrics,
    )
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=settings.max_request_bytes,
        clock=dependencies.clock,
    )
    app.add_middleware(
        AuthenticationMiddleware,
        authenticator=authenticator,
        auth_required=settings.auth_required,
        clock=dependencies.clock,
    )
    app.add_middleware(CorrelationMiddleware, clock=dependencies.clock)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=settings.auth_required,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
        )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(settings.trusted_hosts),
    )
    return app


def build_dependencies_from_settings(
    settings: APISettings,
    *,
    authenticator: Authenticator | None = None,
    firebase_transport: FirebaseTransport | None = None,
) -> ApplicationDependencies:
    """Load only local model references, risk policy, and baselines."""

    required = {
        "artifact_root": settings.artifact_root,
        "model_references_file": settings.model_references_file,
        "risk_policy_file": settings.risk_policy_file,
        "baselines_file": settings.baselines_file,
    }
    missing = tuple(name for name, value in required.items() if value is None)
    if missing:
        raise APIConfigurationError(
            f"Production bootstrap is missing local configuration: {', '.join(missing)}."
        )
    try:
        references = ApprovedModelReferences.model_validate(
            _read_json(settings.model_references_file)
        )
        risk_config = RiskEngineConfig.model_validate(
            _read_json(settings.risk_policy_file)
        )
        if (
            risk_config.left_group_id != settings.left_group_id
            or risk_config.right_group_id != settings.right_group_id
        ):
            raise APIConfigurationError(
                "API and Risk Engine bilateral group configuration disagree."
            )
        store = ExperimentArtifactStore(settings.artifact_root)
        inference = InferenceEngine(store, references)
        risk = ACLRiskEngine(risk_config)
        baselines = InMemoryBaselineRepository.from_json_file(
            settings.baselines_file
        )
    except APIConfigurationError:
        raise
    except Exception as exc:
        raise APIConfigurationError(
            "Local production artifacts failed startup validation."
        ) from exc
    return ApplicationDependencies(
        settings=settings,
        inference_engine=inference,
        risk_engine=risk,
        baseline_repository=baselines,
        checkpoint_store=LocalSessionCheckpointStore(
            settings.checkpoint_directory
        ),
        clock=lambda: datetime.now(timezone.utc),
        authenticator=authenticator,
        firebase_transport=firebase_transport,
    )


def create_app_from_environment() -> FastAPI:
    """Uvicorn factory for offline deployments with optional cloud disabled.

    **Revised — cross-repo contract alignment (DECISIONS.md ADR).**
    Previously this never passed a `firebase_transport`, so setting
    `VIKZAR_FIREBASE_ENABLED=true` would fail startup outright (§`build_
    dependencies_from_settings`'s "no synchronization transport was
    injected" guard) — there was no path from environment variables to a
    real transport. Now: if `VIKZAR_FIREBASE_*` credentials are present
    (`FirebaseCallableTransportConfig.from_environment`), a real
    `FirebaseCallableTransport` is constructed; otherwise `None`, exactly
    as before. This does not itself enable Firebase sync —
    `VIKZAR_FIREBASE_ENABLED` still controls that, per `APISettings`.
    """
    import os

    settings = APISettings.from_environment()
    transport_config = FirebaseCallableTransportConfig.from_environment(dict(os.environ))
    transport = (
        FirebaseCallableTransport(transport_config) if transport_config is not None else None
    )
    return create_app(
        build_dependencies_from_settings(settings, firebase_transport=transport)
    )


def _read_json(path: Path | None) -> object:
    if path is None:
        raise APIConfigurationError("Required local JSON path is absent.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise APIConfigurationError(f"Unable to read local configuration: {path.name}.") from exc


def _install_exception_handlers(app: FastAPI, clock) -> None:
    def correlation(request: Request) -> str:
        return getattr(request.state, "correlation_id", "unbound")

    @app.exception_handler(SessionNotFoundError)
    async def not_found(request: Request, exc: SessionNotFoundError):
        return error_response(
            status_code=404,
            code="SESSION_NOT_FOUND",
            message=str(exc),
            correlation_id=correlation(request),
            clock=clock,
        )

    @app.exception_handler(SessionConflictError)
    async def conflict(request: Request, exc: SessionConflictError):
        return error_response(
            status_code=409,
            code="SESSION_CONFLICT",
            message=str(exc),
            correlation_id=correlation(request),
            clock=clock,
        )

    @app.exception_handler(SessionRecoveryError)
    async def recovery(request: Request, exc: SessionRecoveryError):
        return error_response(
            status_code=409,
            code="SESSION_RECOVERY_FAILED",
            message=str(exc),
            correlation_id=correlation(request),
            clock=clock,
        )

    expected_validation = (
        PipelineOrchestrationError,
        FeatureValidationError,
        InferenceError,
        RiskEngineError,
    )

    async def pipeline_error(request: Request, exc: Exception):
        return error_response(
            status_code=422,
            code="PIPELINE_INPUT_REJECTED",
            message=str(exc),
            correlation_id=correlation(request),
            clock=clock,
        )

    for exception_type in expected_validation:
        app.add_exception_handler(exception_type, pipeline_error)

    @app.exception_handler(RequestValidationError)
    async def request_validation(request: Request, exc: RequestValidationError):
        details = tuple(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return error_response(
            status_code=422,
            code="API_VALIDATION_FAILED",
            message="Request payload validation failed.",
            correlation_id=correlation(request),
            clock=clock,
            details=details,
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        logging.getLogger("app.api").exception(
            "request.unexpected_error",
            extra={
                "event": "request.unexpected_error",
                "exception_type": type(exc).__name__,
            },
        )
        return error_response(
            status_code=500,
            code="API_INTERNAL_ERROR",
            message="An unexpected internal error occurred.",
            correlation_id=correlation(request),
            clock=clock,
        )
