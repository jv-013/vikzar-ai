"""API and local recovery lifecycle tests."""

from __future__ import annotations

import pytest

from app.api.contracts import SessionStartRequest
from app.api.exceptions import SessionConflictError
from app.api.session import SessionManager
from tests.api.helpers import FixedClock, make_player, make_session


def _start_payload():
    return {
        "player": make_player().model_dump(mode="json"),
        "session": make_session().model_dump(mode="json"),
    }


def test_complete_session_lifecycle_and_correlation(api_context) -> None:
    client = api_context["client"]
    headers = {"X-Correlation-ID": "trace-session-001"}

    started = client.post(
        "/api/v1/sessions/start",
        json=_start_payload(),
        headers=headers,
    )
    assert started.status_code == 201
    assert started.headers["X-Correlation-ID"] == "trace-session-001"
    assert started.json()["session"]["state"] == "active"

    assert client.post(
        "/api/v1/sessions/session-001/heartbeat",
        headers=headers,
    ).status_code == 200
    assert client.post(
        "/api/v1/sessions/session-001/disconnect",
        headers=headers,
    ).json()["session"]["state"] == "disconnected"
    assert client.post(
        "/api/v1/sessions/session-001/reconnect",
        headers=headers,
    ).json()["session"]["state"] == "active"
    stopped = client.post(
        "/api/v1/sessions/session-001/stop",
        json={"reason": "completed"},
        headers=headers,
    )
    assert stopped.json()["session"]["state"] == "stopped"
    assert stopped.json()["session"]["stop_reason"] == "completed"
    assert client.post(
        "/api/v1/sessions/session-001/heartbeat",
        headers=headers,
    ).status_code == 409


def test_session_recovery_uses_verified_local_checkpoint(
    api_context,
) -> None:
    store = api_context["store"]
    clock = api_context["clock"]
    first = SessionManager(
        store,
        heartbeat_timeout_seconds=30,
        clock=clock,
    )
    first.start(
        SessionStartRequest(player=make_player(), session=make_session())
    )
    second = SessionManager(
        store,
        heartbeat_timeout_seconds=30,
        clock=clock,
    )

    recovered = second.recover("session-001")

    assert recovered.state.value == "active"
    assert recovered.recovery_count == 1
    with pytest.raises(SessionConflictError):
        second.recover("session-001")


def test_heartbeat_timeout_deterministically_disconnects(api_context) -> None:
    client = api_context["client"]
    client.post("/api/v1/sessions/start", json=_start_payload())
    api_context["clock"].advance(31)

    ready = client.get("/health/ready")

    assert ready.status_code == 200
    assert (
        client.get("/api/v1/sessions/session-001").json()["state"]
        == "disconnected"
    )


def test_graceful_shutdown_stops_active_sessions(api_context) -> None:
    api_context["client"].post("/api/v1/sessions/start", json=_start_payload())
    # The fixture exits after this test. Explicitly exercise the same operation.
    stopped = api_context["app"].state.container.sessions.shutdown()

    assert stopped[0].state.value == "stopped"
    assert stopped[0].stop_reason == "graceful_shutdown"
