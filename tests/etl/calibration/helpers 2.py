"""
Test-only SynchronizedFrame factory for Calibration tests.

Not shipped production code — mirrors the role helpers.py plays for
Synchronization tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Optional

from app.etl.calibration.channel import CalibratedChannel
from app.etl.calibration.reading import CalibratedReading
from app.etl.calibration.unit import PhysicalUnit
from app.etl.synchronization import SyncStatus, SynchronizedFrame
from app.etl.validation.packet import ValidatedPacket


def make_validated_packet(
    device_id: str = "device",
    sequence_number: int = 1,
    device_timestamp_ms: int = 1000,
    raw_channels: Optional[Mapping[str, int]] = None,
) -> ValidatedPacket:
    return ValidatedPacket(
        device_id=device_id,
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        protocol_version=1,
        packet_type=1,
        sequence_number=sequence_number,
        device_timestamp_ms=device_timestamp_ms,
        raw_channels=dict(raw_channels or {"x": 1}),
    )


def make_synchronized_frame(
    group_id: str = "left_lower_limb",
    reference_timestamp: float = 1000.0,
    sync_status: SyncStatus = SyncStatus.MATCHED,
    packets: Optional[Mapping[str, Optional[ValidatedPacket]]] = None,
) -> SynchronizedFrame:
    if packets is None:
        packets = {"primary_motion": make_validated_packet(device_id="smart_pod")}
    return SynchronizedFrame(
        group_id=group_id,
        reference_timestamp=reference_timestamp,
        sync_status=sync_status,
        packets=packets,
    )


def make_calibrated_reading(**overrides) -> CalibratedReading:
    defaults = dict(
        calibrated_channels={"accel_x": CalibratedChannel(1.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)},
        device_id="smart_pod",
        sequence_number=1,
        device_timestamp_ms=1000,
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        protocol_version=1,
    )
    defaults.update(overrides)
    return CalibratedReading(**defaults)
