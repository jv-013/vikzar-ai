"""Health, readiness, environment, startup, and authentication tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import APISettings, ApplicationDependencies, create_app
from app.api.auth import AnonymousAuthenticator
from app.api.dependencies import InMemoryBaselineRepository
from app.api.exceptions import APIConfigurationError
from app.api.session import InMemorySessionCheckpointStore
from tests.api.helpers import (
    ContractInferenceGateway,
    FixedClock,
    StaticAuthenticator,
    default_baseline,
    make_risk_engine,
)


def test_liveness_and_readiness_report_local_authorities(api_context) -> None:
    client = api_context["client"]

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert ready.status_code == 200
    components = {
        item["component"]: item["status"]
        for item in ready.json()["components"]
    }
    assert components["phase8_inference"] == "healthy"
    assert components["phase9_risk"] == "healthy"
    assert components["firebase"] == "disabled"


def test_environment_configuration_is_immutable_and_validated() -> None:
    settings = APISettings.from_environment(
        {
            "VIKZAR_AUTH_REQUIRED": "false",
            "VIKZAR_PORT": "9000",
            "VIKZAR_TRUSTED_HOSTS": "testserver,localhost",
        }
    )

    assert settings.port == 9000
    assert settings.trusted_hosts == ("localhost", "testserver")
    with pytest.raises(ValidationError):
        settings.port = 1  # type: ignore[misc]
    with pytest.raises(ValueError):
        APISettings.from_environment({"VIKZAR_AUTH_REQUIRED": "maybe"})


def test_required_authentication_needs_provider_hook() -> None:
    with pytest.raises(APIConfigurationError):
        create_app(
            ApplicationDependencies(
                settings=APISettings(auth_required=True),
                inference_engine=ContractInferenceGateway(),
                risk_engine=make_risk_engine(),
                baseline_repository=InMemoryBaselineRepository(
                    (default_baseline(),)
                ),
                checkpoint_store=InMemorySessionCheckpointStore(),
                clock=FixedClock(),
            )
        )


def test_authentication_hook_protects_non_health_routes() -> None:
    app = create_app(
        ApplicationDependencies(
            settings=APISettings(auth_required=True, environment="test"),
            inference_engine=ContractInferenceGateway(),
            risk_engine=make_risk_engine(),
            baseline_repository=InMemoryBaselineRepository((default_baseline(),)),
            checkpoint_store=InMemorySessionCheckpointStore(),
            clock=FixedClock(),
            authenticator=StaticAuthenticator(),
        )
    )
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/metrics").status_code == 401
        assert (
            client.get(
                "/metrics",
                headers={"Authorization": "Bearer valid-token"},
            ).status_code
            == 200
        )
