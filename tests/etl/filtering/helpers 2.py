"""
Test-only CalibratedFrame factory for Filtering tests.

Not shipped production code — mirrors the role helpers.py plays for
Calibration and Synchronization tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Optional

from app.etl.calibration import CalibratedChannel, CalibratedFrame, CalibratedReading, PhysicalUnit
from app.etl.filtering.reading import FilteredReading
from app.etl.synchronization import SyncStatus


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


def make_calibrated_frame(
    group_id: str = "left_lower_limb",
    reference_timestamp: float = 1000.0,
    sync_status: SyncStatus = SyncStatus.MATCHED,
    readings: Optional[Mapping[str, CalibratedReading]] = None,
) -> CalibratedFrame:
    if readings is None:
        readings = {"primary_motion": make_calibrated_reading()}
    return CalibratedFrame(
        group_id=group_id,
        reference_timestamp=reference_timestamp,
        sync_status=sync_status,
        readings=readings,
    )


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
