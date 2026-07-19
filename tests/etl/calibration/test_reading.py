"""Unit tests for CalibratedReading."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.etl.calibration.channel import CalibratedChannel
from app.etl.calibration.unit import PhysicalUnit

from .helpers import make_calibrated_reading


def test_rejects_empty_device_id() -> None:
    with pytest.raises(ValueError):
        make_calibrated_reading(device_id="")


def test_calibrated_channels_is_immutable() -> None:
    reading = make_calibrated_reading()

    assert isinstance(reading.calibrated_channels, MappingProxyType)
    with pytest.raises(TypeError):
        reading.calibrated_channels["accel_x"] = CalibratedChannel(0.0, PhysicalUnit.VOLTS)


def test_preserves_provenance_fields() -> None:
    reading = make_calibrated_reading(sequence_number=42, device_timestamp_ms=5000, protocol_version=1)

    assert reading.sequence_number == 42
    assert reading.device_timestamp_ms == 5000
    assert reading.protocol_version == 1


def test_calibrated_reading_has_no_group_id_or_sync_status_fields() -> None:
    """
    Provenance design decision (refinement 2): group_id and sync_status
    are deliberately not duplicated on CalibratedReading — they already
    live on the parent CalibratedFrame.
    """
    reading = make_calibrated_reading()

    assert not hasattr(reading, "group_id")
    assert not hasattr(reading, "sync_status")
    assert not hasattr(reading, "reference_timestamp")
