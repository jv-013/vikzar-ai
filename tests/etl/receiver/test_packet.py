"""Unit tests for RawPacket."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.etl.receiver.packet import RawPacket


def test_raw_packet_stores_fields_unmodified() -> None:
    now = datetime.now(timezone.utc)
    payload = b"\x01\x02\x03"

    packet = RawPacket(device_id="smart_pod", payload=payload, received_at=now)

    assert packet.device_id == "smart_pod"
    assert packet.payload == payload
    assert packet.received_at == now


def test_raw_packet_is_immutable() -> None:
    packet = RawPacket(
        device_id="smart_pod",
        payload=b"\x01",
        received_at=datetime.now(timezone.utc),
    )

    with pytest.raises(FrozenInstanceError):
        packet.device_id = "emg_band"  # type: ignore[misc]


def test_raw_packet_rejects_empty_device_id() -> None:
    with pytest.raises(ValueError):
        RawPacket(device_id="", payload=b"\x01", received_at=datetime.now(timezone.utc))


def test_raw_packet_rejects_non_bytes_payload() -> None:
    with pytest.raises(TypeError):
        RawPacket(
            device_id="smart_pod",
            payload="not bytes",  # type: ignore[arg-type]
            received_at=datetime.now(timezone.utc),
        )
