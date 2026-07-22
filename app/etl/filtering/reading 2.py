"""
FilteredReading: one device's noise-reduced channel values plus the
provenance carried forward from Calibration.

See docs/development/FILTERING_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from app.etl.calibration import CalibratedChannel


@dataclass(frozen=True)
class FilteredReading:
    """
    Noise-reduced channel values from a single source reading.

    Purpose
        Carry filtered values for one device's reading, alongside the
        same provenance CalibratedReading already carried — filtering
        neither adds nor removes provenance, it only replaces each
        channel's value with a noise-reduced one in the same unit.

    Attributes
        filtered_channels: Filtered CalibratedChannel values keyed by
            channel name, matching the source reading's
            calibrated_channels keys except for channels with no
            configured SignalFilter (silently omitted; see Filterer).
            Reuses CalibratedChannel rather than a new wrapper type —
            filtering does not change a value's physical unit.
        device_id: Logical source device, carried from CalibratedReading.
        sequence_number: Carried from CalibratedReading.
        device_timestamp_ms: Carried from CalibratedReading.
        received_at: Carried from CalibratedReading.
        protocol_version: Carried from CalibratedReading.

    Raises
        ValueError: If device_id is empty.
    """

    filtered_channels: Mapping[str, CalibratedChannel]
    device_id: str
    sequence_number: int
    device_timestamp_ms: int
    received_at: datetime
    protocol_version: int

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("FilteredReading.device_id must not be empty.")
        object.__setattr__(
            self, "filtered_channels", MappingProxyType(dict(self.filtered_channels))
        )
