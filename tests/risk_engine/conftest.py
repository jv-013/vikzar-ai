"""Shared Phase 9 fixtures."""

from __future__ import annotations

import pytest

from app.risk_engine import ACLRiskEngine
from tests.risk_engine.helpers import make_config, make_request


@pytest.fixture
def risk_config():
    return make_config()


@pytest.fixture
def risk_engine(risk_config):
    return ACLRiskEngine(risk_config)


@pytest.fixture
def low_risk_request():
    return make_request()


@pytest.fixture
def high_risk_request():
    return make_request(high_risk=True)
