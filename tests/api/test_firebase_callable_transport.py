"""Tests for the real (Cloud-Function-calling) FirebaseTransport
implementation — HTTP interactions are mocked (no network), but the
request-building/token-refresh/error-handling logic is exercised for
real."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.api.firebase_callable_transport import (
    FirebaseCallableTransport,
    FirebaseCallableTransportConfig,
)
from app.api.ingestion_contracts import IngestLiveTickPayload, LiveTickMetrics


def _config() -> FirebaseCallableTransportConfig:
    return FirebaseCallableTransportConfig(
        project_id="vikzar-prod",
        region="us-central1",
        api_key="test-api-key",
        refresh_token="test-refresh-token",
    )


def _tick_payload() -> IngestLiveTickPayload:
    return IngestLiveTickPayload(
        session_id="s1",
        player_id="p1",
        sequence_number=1,
        tick_timestamp=datetime(2026, 7, 19, tzinfo=timezone.utc),
        connection_status="connected",
        metrics=LiveTickMetrics(
            current_load=1.0, cumulative_impacts=0, risk_score=0.1, risk_level="low"
        ),
    )


class _FakeResponse:
    def __init__(self, json_body: dict, status_code: int = 200) -> None:
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._json_body


def test_from_environment_returns_none_when_secrets_are_absent() -> None:
    assert FirebaseCallableTransportConfig.from_environment({}) is None


def test_from_environment_builds_config_from_vikzar_prefixed_vars() -> None:
    config = FirebaseCallableTransportConfig.from_environment(
        {
            "VIKZAR_FIREBASE_PROJECT_ID": "vikzar-prod",
            "VIKZAR_FIREBASE_API_KEY": "key",
            "VIKZAR_FIREBASE_INGESTION_REFRESH_TOKEN": "token",
        }
    )
    assert config is not None
    assert config.project_id == "vikzar-prod"
    assert config.region == "us-central1"  # default


@pytest.mark.asyncio
async def test_id_token_is_fetched_and_cached() -> None:
    transport = FirebaseCallableTransport(_config())
    transport._client.post = AsyncMock(  # type: ignore[method-assign]
        return_value=_FakeResponse({"id_token": "abc123", "expires_in": "3600"})
    )

    token_1 = await transport._id_token()
    token_2 = await transport._id_token()

    assert token_1 == "abc123"
    assert token_2 == "abc123"
    # Cached — only one refresh call for two token reads.
    assert transport._client.post.call_count == 1
    await transport.close()


@pytest.mark.asyncio
async def test_call_ingest_live_tick_posts_the_wire_payload_with_bearer_token() -> None:
    transport = FirebaseCallableTransport(_config())
    responses = [
        _FakeResponse({"id_token": "abc123", "expires_in": "3600"}),
        _FakeResponse({"result": {"sessionId": "s1", "sequenceNumber": 1}}),
    ]
    transport._client.post = AsyncMock(side_effect=responses)  # type: ignore[method-assign]

    await transport.call_ingest_live_tick(_tick_payload())

    call_url = transport._client.post.call_args_list[1].args[0]
    call_kwargs = transport._client.post.call_args_list[1].kwargs
    assert call_url == "https://us-central1-vikzar-prod.cloudfunctions.net/ingestLiveTick"
    assert call_kwargs["headers"]["Authorization"] == "Bearer abc123"
    assert call_kwargs["json"]["data"]["sessionId"] == "s1"
    await transport.close()


@pytest.mark.asyncio
async def test_call_raises_on_callable_error_envelope() -> None:
    transport = FirebaseCallableTransport(_config())
    responses = [
        _FakeResponse({"id_token": "abc123", "expires_in": "3600"}),
        _FakeResponse({"error": {"status": "PERMISSION_DENIED", "message": "not authorized"}}),
    ]
    transport._client.post = AsyncMock(side_effect=responses)  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="PERMISSION_DENIED"):
        await transport.call_ingest_live_tick(_tick_payload())
    await transport.close()


@pytest.mark.asyncio
async def test_health_returns_false_when_token_refresh_fails() -> None:
    transport = FirebaseCallableTransport(_config())
    transport._client.post = AsyncMock(side_effect=RuntimeError("network down"))  # type: ignore[method-assign]

    assert await transport.health() is False
    await transport.close()
