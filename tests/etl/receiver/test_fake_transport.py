"""Unit tests for FakeBLETransport."""

from __future__ import annotations

import asyncio

import pytest

from app.etl.receiver.exceptions import BLEDeviceNotFoundError
from app.etl.receiver.fake_transport import FakeBLETransport


@pytest.mark.asyncio
async def test_connect_and_disconnect_track_connection_state() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({"smart_pod"}))

    assert not transport.is_connected("smart_pod")

    await transport.connect("smart_pod", timeout_seconds=1.0)
    assert transport.is_connected("smart_pod")

    await transport.disconnect("smart_pod")
    assert not transport.is_connected("smart_pod")


@pytest.mark.asyncio
async def test_connect_to_unknown_device_raises() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({"smart_pod"}))

    with pytest.raises(BLEDeviceNotFoundError):
        await transport.connect("unknown_device", timeout_seconds=1.0)


@pytest.mark.asyncio
async def test_connect_failures_are_simulated_before_success() -> None:
    transport = FakeBLETransport(
        known_device_ids=frozenset({"smart_pod"}),
        connect_failures={"smart_pod": 2},
    )

    with pytest.raises(ConnectionError):
        await transport.connect("smart_pod", timeout_seconds=1.0)
    with pytest.raises(ConnectionError):
        await transport.connect("smart_pod", timeout_seconds=1.0)

    await transport.connect("smart_pod", timeout_seconds=1.0)
    assert transport.is_connected("smart_pod")


@pytest.mark.asyncio
async def test_emit_requires_connection() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({"smart_pod"}))
    transport.set_notification_handler(lambda device_id, payload: None)

    with pytest.raises(BLEDeviceNotFoundError):
        transport.emit("smart_pod", b"\x01")


@pytest.mark.asyncio
async def test_emit_requires_registered_handler() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({"smart_pod"}))
    await transport.connect("smart_pod", timeout_seconds=1.0)

    with pytest.raises(RuntimeError):
        transport.emit("smart_pod", b"\x01")


@pytest.mark.asyncio
async def test_emit_invokes_notification_handler_with_unmodified_payload() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({"smart_pod"}))
    received: list[tuple[str, bytes]] = []
    transport.set_notification_handler(lambda device_id, payload: received.append((device_id, payload)))
    await transport.connect("smart_pod", timeout_seconds=1.0)

    transport.emit("smart_pod", b"\xde\xad\xbe\xef")

    assert received == [("smart_pod", b"\xde\xad\xbe\xef")]


@pytest.mark.asyncio
async def test_simulate_unexpected_disconnect_invokes_disconnect_handler() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({"smart_pod"}))
    disconnected: list[str] = []
    transport.set_disconnect_handler(disconnected.append)
    await transport.connect("smart_pod", timeout_seconds=1.0)

    transport.simulate_unexpected_disconnect("smart_pod")

    assert disconnected == ["smart_pod"]
    assert not transport.is_connected("smart_pod")


@pytest.mark.asyncio
async def test_start_synthetic_stream_emits_until_disconnected() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({"smart_pod"}))
    received: list[bytes] = []
    transport.set_notification_handler(lambda device_id, payload: received.append(payload))
    await transport.connect("smart_pod", timeout_seconds=1.0)

    stream_task = asyncio.ensure_future(
        transport.start_synthetic_stream(
            "smart_pod", interval_seconds=0.01, payload_factory=lambda: b"\x00"
        )
    )
    await asyncio.sleep(0.05)
    await transport.disconnect("smart_pod")
    await stream_task

    assert len(received) >= 1
    assert all(payload == b"\x00" for payload in received)
