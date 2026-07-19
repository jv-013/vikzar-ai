"""
Per-device reference-timestamp resolution.

See docs/development/SYNCHRONIZATION_DESIGN.md, sections 7 and 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from app.config import etl_config


@dataclass
class _DeviceClockState:
    offset_ms: float
    last_device_timestamp_ms: int
    last_sequence_number: int
    last_reference_timestamp_ms: float


class ReferenceTimestampResolver:
    """
    Resolves a common, host-relative reference_timestamp (milliseconds)
    for packets arriving from independently-clocked devices.

    Purpose
        Two devices in the same synchronization group boot
        independently and have no shared clock. This resolver makes
        their timestamps comparable without ever reconciling clocks
        *across* devices belonging to different groups — it tracks
        state per device_id only, scoped to whichever group owns it.

    Precedence (docs/development/SYNCHRONIZATION_DESIGN.md, section 7):
        1. Device timestamp, anchored once per device against host
           receive time on that device's first packet, then used via
           device-clock deltas thereafter (low jitter — crystal-clock
           accurate between consecutive packets from one device).
        2. Sequence number, used only for the single transitional
           packet where a device's clock is detected to have reset
           (gone backward) — signals a mid-session reboot.
        3. Host receive time, used implicitly as the anchor for a
           device's very first packet (see tier 1) — not a separate
           code path.
    """

    def __init__(self) -> None:
        self._state: Dict[str, _DeviceClockState] = {}

    def resolve(
        self,
        device_id: str,
        device_timestamp_ms: int,
        sequence_number: int,
        received_at: datetime,
    ) -> float:
        """
        Resolve one packet's reference_timestamp.

        Args:
            device_id: The originating device. State is tracked
                independently per device_id.
            device_timestamp_ms: The packet's device-reported timestamp.
            sequence_number: The packet's device-assigned sequence
                number, used only on a detected clock reset.
            received_at: Host reception time, used to anchor a device's
                first packet.

        Returns:
            The resolved reference_timestamp, in milliseconds.
        """
        received_at_ms = received_at.timestamp() * 1000.0
        state = self._state.get(device_id)

        if state is None:
            reference_timestamp_ms = received_at_ms
            offset_ms = reference_timestamp_ms - device_timestamp_ms
        elif device_timestamp_ms < state.last_device_timestamp_ms:
            reference_timestamp_ms = self._estimate_from_sequence(state, sequence_number)
            offset_ms = received_at_ms - device_timestamp_ms
        else:
            offset_ms = state.offset_ms
            reference_timestamp_ms = device_timestamp_ms + offset_ms

        self._state[device_id] = _DeviceClockState(
            offset_ms=offset_ms,
            last_device_timestamp_ms=device_timestamp_ms,
            last_sequence_number=sequence_number,
            last_reference_timestamp_ms=reference_timestamp_ms,
        )
        return reference_timestamp_ms

    def _estimate_from_sequence(
        self, state: _DeviceClockState, sequence_number: int
    ) -> float:
        sequence_delta = sequence_number - state.last_sequence_number
        return (
            state.last_reference_timestamp_ms
            + sequence_delta * etl_config.NOMINAL_SAMPLE_INTERVAL_MS
        )
