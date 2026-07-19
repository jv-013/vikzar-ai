"""
Test-only Window/FilteredFrame factories for Feature Extraction tests.

Not shipped production code — mirrors the role helpers.py plays for
every other ETL stage's tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence, Tuple

from app.etl.calibration import CalibratedChannel, PhysicalUnit
from app.etl.filtering import FilteredFrame
from app.etl.filtering.reading import FilteredReading
from app.etl.synchronization import SyncStatus
from app.etl.windowing import Window


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


def make_motion_frame(
    reference_timestamp: float,
    accel: Optional[Tuple[float, float, float]] = (1.0, 0.0, 0.0),
    gyro: Optional[Tuple[float, float, float]] = None,
    group_id: str = "left_lower_limb",
) -> FilteredFrame:
    channels = {}
    if accel is not None:
        channels["accel_x"] = CalibratedChannel(accel[0], PhysicalUnit.METERS_PER_SECOND_SQUARED)
        channels["accel_y"] = CalibratedChannel(accel[1], PhysicalUnit.METERS_PER_SECOND_SQUARED)
        channels["accel_z"] = CalibratedChannel(accel[2], PhysicalUnit.METERS_PER_SECOND_SQUARED)
    if gyro is not None:
        channels["gyro_x"] = CalibratedChannel(gyro[0], PhysicalUnit.DEGREES_PER_SECOND)
        channels["gyro_y"] = CalibratedChannel(gyro[1], PhysicalUnit.DEGREES_PER_SECOND)
        channels["gyro_z"] = CalibratedChannel(gyro[2], PhysicalUnit.DEGREES_PER_SECOND)
    reading = make_filtered_reading(filtered_channels=channels)
    return make_filtered_frame(
        group_id=group_id, reference_timestamp=reference_timestamp, readings={"primary_motion": reading}
    )


def make_pressure_frame(
    reference_timestamp: float,
    loads: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    group_id: str = "left_lower_limb",
) -> FilteredFrame:
    channels = {
        "fsr_1": CalibratedChannel(loads[0], PhysicalUnit.DEVELOPMENT_PLACEHOLDER),
        "fsr_2": CalibratedChannel(loads[1], PhysicalUnit.DEVELOPMENT_PLACEHOLDER),
        "fsr_3": CalibratedChannel(loads[2], PhysicalUnit.DEVELOPMENT_PLACEHOLDER),
    }
    reading = make_filtered_reading(filtered_channels=channels)
    return make_filtered_frame(
        group_id=group_id, reference_timestamp=reference_timestamp, readings={"primary_motion": reading}
    )


def make_emg_frame(
    reference_timestamp: float,
    quadriceps: Optional[float] = None,
    hamstring: Optional[float] = None,
    group_id: str = "left_lower_limb",
) -> FilteredFrame:
    channels = {}
    if quadriceps is not None:
        channels["quadriceps"] = CalibratedChannel(quadriceps, PhysicalUnit.VOLTS)
    if hamstring is not None:
        channels["hamstring"] = CalibratedChannel(hamstring, PhysicalUnit.VOLTS)

    readings = {"primary_motion": make_filtered_reading()}
    if channels:
        readings["emg"] = make_filtered_reading(filtered_channels=channels, device_id="emg_band")
    return make_filtered_frame(group_id=group_id, reference_timestamp=reference_timestamp, readings=readings)


def make_window(
    frames: Sequence[FilteredFrame],
    group_id: str = "left_lower_limb",
    window_specification_name: str = "primary",
    window_start: float = 0.0,
    window_end: float = 1000.0,
) -> Window:
    return Window(
        group_id=group_id,
        window_specification_name=window_specification_name,
        window_start=window_start,
        window_end=window_end,
        frames=frames,
    )
