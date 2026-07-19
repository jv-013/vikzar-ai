"""
FilteredFrame: the internal contract between Filtering and Sliding Window.

FilteredFrame is an ETL-internal type only, like RawPacket,
ValidatedPacket, SynchronizedFrame, and CalibratedFrame. It must never
be imported outside app/etl and has no relationship to RawFeatureVector
or EnhancedFeatureVector.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.etl.synchronization import SyncStatus

from .reading import FilteredReading


@dataclass(frozen=True)
class FilteredFrame:
    """
    One synchronization group's noise-reduced data.

    Purpose
        Carry a synchronization group's filtered primary_motion
        reading, and its filtered (or explicitly absent) emg reading,
        to Sliding Window. Shape mirrors CalibratedFrame exactly —
        group_id, reference_timestamp, and sync_status are carried
        through unchanged (Decision 022's group_id preservation
        contract) — but FilteredFrame is a structurally distinct type
        with no shared base or fields, so it can never be mistaken for
        a CalibratedFrame and fed back into Filtering.

    Attributes
        group_id: Preserved unchanged from the source CalibratedFrame.
        reference_timestamp: Preserved unchanged from the source
            CalibratedFrame.
        sync_status: Preserved unchanged from the source CalibratedFrame.
        readings: Always contains a "primary_motion" entry. Contains an
            "emg" entry only when the source CalibratedFrame did.

    Raises
        ValueError: If group_id is empty or "primary_motion" is missing.
    """

    group_id: str
    reference_timestamp: float
    sync_status: SyncStatus
    readings: Mapping[str, FilteredReading]

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("FilteredFrame.group_id must not be empty.")
        if "primary_motion" not in self.readings:
            raise ValueError(
                "FilteredFrame.readings must contain a 'primary_motion' entry."
            )
        object.__setattr__(self, "readings", MappingProxyType(dict(self.readings)))
