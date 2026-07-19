"""
Test-only FilteredFrame factory for Windowing tests.

Not shipped production code — mirrors the role helpers.py plays for
every other ETL stage's tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Optional

from app.etl.calibration import CalibratedChannel, PhysicalUnit
from app.etl.filtering import FilteredFrame
from app.etl.filtering.reading import FilteredReading
from app.etl.synchronization import SyncStatus


def make_filtered_reading(**overrides) -> FilteredReading:
    defaults = dict(
        filtered_channels={"accel_x": CalibratedChannel(1.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)},
        device_id="smart_pod",
        sequence_number=1,
        device_timestamp_ms=1000,
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        protocol_version=1,
    )
    defaults.update(overrides)
    return FilteredReading(**defaults)


def make_filtered_frame(
    group_id: str = "left_lower_limb",
    reference_timestamp: float = 0.0,
    sync_status: SyncStatus = SyncStatus.MATCHED,
    readings: Optional[Mapping[str, FilteredReading]] = None,
) -> FilteredFrame:
    if readings is None:
        readings = {"primary_motion": make_filtered_reading()}
    return FilteredFrame(
        group_id=group_id,
        reference_timestamp=reference_timestamp,
        sync_status=sync_status,
        readings=readings,
    )
