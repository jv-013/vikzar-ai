"""
CalibratedReading: one device's calibrated channel values plus the
provenance needed to trace them back to their source packet.

See docs/development/CALIBRATION_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from .channel import CalibratedChannel


@dataclass(frozen=True)
class CalibratedReading:
    """
    Calibrated channel values from a single source packet.

    Purpose
        Carry calibrated values for one device's reading, alongside the
        minimal provenance needed to trace it back to its source
        ValidatedPacket for debugging.

    Provenance design
        group_id and sync_status are deliberately not repeated here —
        they already live on the parent CalibratedFrame, and duplicating
        them would re-introduce the same identity-duplication problem
        Decision 024 removed from the EMG Band payload. reference_timestamp
        is also deliberately absent: SynchronizedFrame only preserves the
        frame-level reference_timestamp (equal to primary_motion's own);
        the emg packet's individually-resolved timestamp is computed and
        discarded inside GroupSynchronizer during matching and is not
        exposed by the frozen Synchronization contract. Inventing one
        here would violate the project's no-fabrication discipline.

    Attributes
        calibrated_channels: Calibrated values keyed by channel name
            (e.g. "accel_x"), matching the source packet's raw_channels
            keys except for channels with no configured
            CalibrationFunction (silently omitted; see Calibrator).
        device_id: Logical source device, carried from ValidatedPacket.
        sequence_number: Device-assigned sequence number, carried from
            ValidatedPacket.
        device_timestamp_ms: Device-reported timestamp, carried from
            ValidatedPacket.
        received_at: Host reception timestamp, carried from
            ValidatedPacket.
        protocol_version: Wire protocol version, carried from
            ValidatedPacket.

    Raises
        ValueError: If device_id is empty.
    """

    calibrated_channels: Mapping[str, CalibratedChannel]
    device_id: str
    sequence_number: int
    device_timestamp_ms: int
    received_at: datetime
    protocol_version: int

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("CalibratedReading.device_id must not be empty.")
        object.__setattr__(
            self, "calibrated_channels", MappingProxyType(dict(self.calibrated_channels))
        )
