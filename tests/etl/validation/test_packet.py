"""Unit tests for ValidatedPacket."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from app.etl.validation.packet import ValidatedPacket


def _make(**overrides) -> ValidatedPacket:
    defaults = dict(
        device_id="smart_pod",
        received_at=datetime.now(timezone.utc),
        protocol_version=1,
        packet_type=1,
        sequence_number=0,
        device_timestamp_ms=0,
        raw_channels={"accel_x": 1},
    )
    defaults.update(overrides)
    return ValidatedPacket(**defaults)


def test_stores_fields_unmodified() -> None:
    packet = _make(sequence_number=42, device_timestamp_ms=1000)
    assert packet.device_id == "smart_pod"
    assert packet.protocol_version == 1
    assert packet.packet_type == 1
    assert packet.sequence_number == 42
    assert packet.device_timestamp_ms == 1000
    assert dict(packet.raw_channels) == {"accel_x": 1}


def test_raw_channels_is_read_only() -> None:
    packet = _make()
    assert isinstance(packet.raw_channels, MappingProxyType)
    with pytest.raises(TypeError):
        packet.raw_channels["accel_x"] = 999  # type: ignore[index]


def test_is_immutable() -> None:
    packet = _make()
    with pytest.raises(FrozenInstanceError):
        packet.device_id = "other"  # type: ignore[misc]


def test_rejects_empty_device_id() -> None:
    with pytest.raises(ValueError):
        _make(device_id="")


def test_rejects_empty_raw_channels() -> None:
    with pytest.raises(ValueError):
        _make(raw_channels={})
