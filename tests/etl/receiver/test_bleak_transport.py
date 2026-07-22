"""Tests for the real bleak-based BLETransport. `bleak.BleakClient` itself
is mocked — no physical BLE hardware exists to test against — but the
retry/backoff, notification-routing, and disconnect-handling logic
around it is exercised for real."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.exc import BleakError

from app.etl.receiver.bleak_transport import BleakBLETransport
from app.etl.receiver.exceptions import BLEConnectionError, BLEDeviceNotFoundError


def _transport(**overrides) -> BleakBLETransport:
    defaults = dict(
        address_by_device_id={"smart_pod": "AA:BB:CC:DD:EE:FF"},
        notify_characteristic_uuid="0000ffe1-0000-1000-8000-00805f9b34fb",
        max_connect_attempts=2,
        reconnect_backoff_seconds=0.0,
    )
    defaults.update(overrides)
    return BleakBLETransport(**defaults)


@pytest.mark.asyncio
async def test_connect_raises_device_not_found_for_an_unmapped_logical_id() -> None:
    transport = _transport()
    with pytest.raises(BLEDeviceNotFoundError):
        await transport.connect("unknown_device", timeout_seconds=1.0)


@pytest.mark.asyncio
async def test_connect_succeeds_and_marks_device_connected() -> None:
    fake_client = MagicMock()
    fake_client.connect = AsyncMock()
    fake_client.start_notify = AsyncMock()
    fake_client.is_connected = True

    with patch("app.etl.receiver.bleak_transport.BleakClient", return_value=fake_client):
        transport = _transport()
        await transport.connect("smart_pod", timeout_seconds=5.0)

    assert transport.is_connected("smart_pod") is True
    fake_client.connect.assert_awaited_once()
    fake_client.start_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_retries_then_raises_ble_connection_error_after_exhausting_attempts() -> None:
    fake_client = MagicMock()
    fake_client.connect = AsyncMock(side_effect=BleakError("no route to device"))

    with patch("app.etl.receiver.bleak_transport.BleakClient", return_value=fake_client):
        transport = _transport(max_connect_attempts=3)
        with pytest.raises(BLEConnectionError):
            await transport.connect("smart_pod", timeout_seconds=1.0)

    assert fake_client.connect.await_count == 3
    assert transport.is_connected("smart_pod") is False


@pytest.mark.asyncio
async def test_notification_handler_receives_device_id_and_bytes_payload() -> None:
    captured: list[tuple[str, bytes]] = []
    fake_client = MagicMock()
    fake_client.connect = AsyncMock()
    fake_client.is_connected = True

    async def fake_start_notify(_uuid, callback):
        callback(0, bytearray(b"\x01\x02\x03"))

    fake_client.start_notify = AsyncMock(side_effect=fake_start_notify)

    with patch("app.etl.receiver.bleak_transport.BleakClient", return_value=fake_client):
        transport = _transport()
        transport.set_notification_handler(lambda device_id, payload: captured.append((device_id, payload)))
        await transport.connect("smart_pod", timeout_seconds=5.0)

    assert captured == [("smart_pod", b"\x01\x02\x03")]


@pytest.mark.asyncio
async def test_unexpected_disconnect_invokes_disconnect_handler_and_clears_state() -> None:
    disconnected: list[str] = []
    fake_client = MagicMock()
    fake_client.connect = AsyncMock()
    fake_client.start_notify = AsyncMock()
    fake_client.is_connected = True

    with patch("app.etl.receiver.bleak_transport.BleakClient") as client_cls:
        client_cls.return_value = fake_client
        transport = _transport()
        transport.set_disconnect_handler(lambda device_id: disconnected.append(device_id))
        await transport.connect("smart_pod", timeout_seconds=5.0)

        # Simulate bleak invoking our disconnected_callback (captured from the constructor call).
        disconnected_callback = client_cls.call_args.kwargs["disconnected_callback"]
        disconnected_callback(fake_client)

    assert disconnected == ["smart_pod"]
    assert transport.is_connected("smart_pod") is False


@pytest.mark.asyncio
async def test_disconnect_is_a_no_op_for_an_unconnected_device() -> None:
    transport = _transport()
    await transport.disconnect("smart_pod")  # must not raise
    assert transport.is_connected("smart_pod") is False
