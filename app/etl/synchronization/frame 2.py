"""
SynchronizedFrame: the internal contract between Synchronization and
Calibration.

SynchronizedFrame is an ETL-internal type only, like RawPacket and
ValidatedPacket. It must never be imported outside app/etl and has no
relationship to RawFeatureVector or EnhancedFeatureVector.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional

from app.etl.validation import ValidatedPacket


class SyncStatus(str, Enum):
    """
    How a SynchronizedFrame's data came to be assembled.

    MATCHED
        The primary_motion and emg packets were paired within
        sync_tolerance.
    TIMED_OUT
        A primary_motion packet's emg partner did not arrive within
        sync_timeout. Emitted anyway — primary_motion data is never
        discarded — with the emg slot explicitly absent.
    NOT_REQUIRED
        This group has no emg device configured this session (e.g.
        Match Mode). No emg slot exists on the frame at all.
    """

    MATCHED = "matched"
    TIMED_OUT = "timed_out"
    NOT_REQUIRED = "not_required"


@dataclass(frozen=True)
class SynchronizedFrame:
    """
    One temporally-aligned unit of data for a single synchronization
    group.

    Purpose
        Carry a synchronization group's primary_motion packet, and its
        matched (or explicitly absent) emg packet, to Calibration.
        Structural/temporal alignment is guaranteed here; no
        interpretation of channel values, and no comparison against any
        other synchronization group, occurs at this stage or any stage
        that produced this frame (Decision 022).

    Attributes
        group_id: Which synchronization group this frame belongs to.
            Preserved unchanged by every ETL stage from here through to
            the ETL→AI boundary (Decision 022).
        reference_timestamp: This frame's anchor time, in milliseconds
            on the primary_motion device's own resolved timeline. Never
            an average or a cross-group value.
        sync_status: How this frame's data was assembled. See
            SyncStatus.
        packets: Always contains a "primary_motion" entry (never None).
            Contains an "emg" entry only when this group has an emg
            device configured this session; its value is None when
            sync_status is TIMED_OUT.

    Raises
        ValueError: If group_id is empty, "primary_motion" is missing,
            or "primary_motion" is None.
    """

    group_id: str
    reference_timestamp: float
    sync_status: SyncStatus
    packets: Mapping[str, Optional[ValidatedPacket]]

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("SynchronizedFrame.group_id must not be empty.")
        if "primary_motion" not in self.packets:
            raise ValueError(
                "SynchronizedFrame.packets must contain a 'primary_motion' entry."
            )
        if self.packets["primary_motion"] is None:
            raise ValueError("SynchronizedFrame.packets['primary_motion'] must not be None.")
        object.__setattr__(self, "packets", MappingProxyType(dict(self.packets)))
