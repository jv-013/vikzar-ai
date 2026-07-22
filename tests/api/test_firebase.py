"""Cloud-Function-call-shaped Firebase synchronization and deferred-delivery tests."""

from __future__ import annotations

import pytest

from app.api.firebase import FirebaseSynchronizer
from tests.api.helpers import (
    FakeFirebaseTransport,
    make_player,
    make_raw_feature_vector,
    make_session,
)


def _start(client):
    return client.post(
        "/api/v1/sessions/start",
        json={
            "player": make_player().model_dump(mode="json"),
            "session": make_session().model_dump(mode="json"),
        },
    )


def test_firebase_calls_ingest_live_tick_with_no_raw_data(firebase_context) -> None:
    client = firebase_context["client"]
    transport = firebase_context["transport"]
    _start(client)
    response = client.post(
        "/api/v1/sessions/session-001/feature-vectors",
        json={
            "feature_vector": make_raw_feature_vector().model_dump(mode="json")
        },
    )

    assert response.status_code == 200
    assert len(transport.live_ticks) == 1
    tick = transport.live_ticks[0]
    assert tick.session_id == "session-001"
    assert 0.0 <= tick.metrics.risk_score <= 1.0

    # Never a raw sensor sample or feature vector, per BACKEND_SPECIFICATION.md §0.
    serialized = str(transport.live_ticks).lower() + str(transport.alerts).lower()
    assert "feature_vector" not in serialized
    assert "raw_imu" not in serialized
    assert "raw_emg" not in serialized


@pytest.mark.asyncio
async def test_firebase_failure_queues_and_reconnect_flushes() -> None:
    from app.api.ingestion_contracts import IngestLiveTickPayload, LiveTickMetrics
    from datetime import datetime, timezone

    transport = FakeFirebaseTransport(fail=True)
    sync = FirebaseSynchronizer(transport, enabled=True, queue_capacity=10)

    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    result = await sync._deliver(
        "call_ingest_live_tick",
        IngestLiveTickPayload(
            session_id="session-001",
            player_id="player-001",
            sequence_number=1,
            tick_timestamp=now,
            connection_status="connected",
            metrics=LiveTickMetrics(
                current_load=10.0,
                cumulative_impacts=0,
                risk_score=0.1,
                risk_level="low",
            ),
        ),
    )
    assert result.status.value == "queued"
    transport.fail = False

    assert await sync.flush() == 1
    assert sync.queued_count == 0


@pytest.mark.asyncio
async def test_sync_session_is_honestly_disabled_pending_schema_extension() -> None:
    """`SessionStartRequest`/`Session` carry no `type`/`deviceIds`
    (BACKEND_SPECIFICATION.md §21.3 requires both) — `sync_session` must
    report this honestly rather than fabricate them. See `firebase.py`."""
    from app.api.contracts import SessionLifecycleState, SessionSnapshot

    transport = FakeFirebaseTransport()
    sync = FirebaseSynchronizer(transport, enabled=True, queue_capacity=10)
    from datetime import datetime, timezone

    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    result = await sync.sync_session(
        SessionSnapshot(
            session_id="session-001",
            player_id="player-001",
            state=SessionLifecycleState.ACTIVE,
            started_at=now,
            last_heartbeat_at=now,
            prediction_count=0,
            recovery_count=0,
        )
    )
    assert result.status.value == "disabled"
    assert transport.live_ticks == []
    assert transport.alerts == []
