"""Shared FastAPI application fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import APISettings, ApplicationDependencies, create_app
from app.api.dependencies import InMemoryBaselineRepository
from app.api.session import InMemorySessionCheckpointStore
from tests.api.helpers import (
    ContractInferenceGateway,
    FakeFirebaseTransport,
    FixedClock,
    default_baseline,
    make_risk_engine,
)


@pytest.fixture
def api_context():
    clock = FixedClock()
    inference = ContractInferenceGateway()
    store = InMemorySessionCheckpointStore()
    settings = APISettings(auth_required=False, environment="test")
    dependencies = ApplicationDependencies(
        settings=settings,
        inference_engine=inference,
        risk_engine=make_risk_engine(),
        baseline_repository=InMemoryBaselineRepository((default_baseline(),)),
        checkpoint_store=store,
        clock=clock,
    )
    app = create_app(dependencies)
    with TestClient(app) as client:
        yield {
            "app": app,
            "client": client,
            "clock": clock,
            "inference": inference,
            "store": store,
        }


@pytest.fixture
def firebase_context():
    clock = FixedClock()
    inference = ContractInferenceGateway()
    transport = FakeFirebaseTransport()
    settings = APISettings(
        auth_required=False,
        firebase_enabled=True,
        environment="test",
    )
    dependencies = ApplicationDependencies(
        settings=settings,
        inference_engine=inference,
        risk_engine=make_risk_engine(),
        baseline_repository=InMemoryBaselineRepository((default_baseline(),)),
        checkpoint_store=InMemorySessionCheckpointStore(),
        clock=clock,
        firebase_transport=transport,
    )
    app = create_app(dependencies)
    with TestClient(app) as client:
        yield {"client": client, "transport": transport, "app": app}
