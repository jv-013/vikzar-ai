"""Unit tests for FilteredReading."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.etl.calibration import CalibratedChannel, PhysicalUnit

from .helpers import make_filtered_reading


def test_rejects_empty_device_id() -> None:
    with pytest.raises(ValueError):
        make_filtered_reading(device_id="")


def test_filtered_channels_is_immutable() -> None:
    reading = make_filtered_reading()

    assert isinstance(reading.filtered_channels, MappingProxyType)
    with pytest.raises(TypeError):
        reading.filtered_channels["accel_x"] = CalibratedChannel(0.0, PhysicalUnit.VOLTS)


def test_preserves_provenance_fields() -> None:
    reading = make_filtered_reading(sequence_number=42, device_timestamp_ms=5000, protocol_version=1)

    assert reading.sequence_number == 42
    assert reading.device_timestamp_ms == 5000
    assert reading.protocol_version == 1
