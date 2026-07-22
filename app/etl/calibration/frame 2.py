"""
CalibratedFrame: the internal contract between Calibration and Filtering.

CalibratedFrame is an ETL-internal type only, like RawPacket,
ValidatedPacket, and SynchronizedFrame. It must never be imported outside
app/etl and has no relationship to RawFeatureVector or
EnhancedFeatureVector.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.etl.synchronization import SyncStatus

from .reading import CalibratedReading


@dataclass(frozen=True)
class CalibratedFrame:
    """
    One synchronization group's calibrated data.

    Purpose
        Carry a synchronization group's calibrated primary_motion
        reading, and its calibrated (or explicitly absent) emg reading,
        to Filtering. Structural shape mirrors SynchronizedFrame
        exactly — group_id, reference_timestamp, and sync_status are
        carried through unchanged (Decision 022's group_id preservation
        contract) — but CalibratedFrame is a structurally distinct type
        with no shared base or fields, so it can never be mistaken for
        a SynchronizedFrame and fed back into Calibration.

    Attributes
        group_id: Which synchronization group this frame belongs to.
            Preserved unchanged from the source SynchronizedFrame.
        reference_timestamp: Preserved unchanged from the source
            SynchronizedFrame.
        sync_status: Preserved unchanged from the source
            SynchronizedFrame.
        readings: Always contains a "primary_motion" entry. Contains an
            "emg" entry only when the source SynchronizedFrame did
            (i.e. sync_status was MATCHED for this frame's emg slot);
            absent entirely for NOT_REQUIRED and TIMED_OUT groups,
            never fabricated.

    Raises
        ValueError: If group_id is empty or "primary_motion" is missing.
    """

    group_id: str
    reference_timestamp: float
    sync_status: SyncStatus
    readings: Mapping[str, CalibratedReading]

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("CalibratedFrame.group_id must not be empty.")
        if "primary_motion" not in self.readings:
            raise ValueError(
                "CalibratedFrame.readings must contain a 'primary_motion' entry."
            )
        object.__setattr__(self, "readings", MappingProxyType(dict(self.readings)))
