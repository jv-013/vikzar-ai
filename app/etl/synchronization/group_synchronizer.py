"""
GroupSynchronizer: buffering, matching, and timeout logic for exactly one
synchronization group.

See docs/development/SYNCHRONIZATION_DESIGN.md, sections 4-10.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from app.config import etl_config
from app.etl.validation import ValidatedPacket

from .frame import SyncStatus, SynchronizedFrame
from .timestamp import ReferenceTimestampResolver

logger = logging.getLogger(__name__)

PRIMARY_MOTION_ROLE = "primary_motion"
"""Every synchronization group's mandatory motion/kinetic sensor role."""

EMG_ROLE = "emg"
"""A synchronization group's optional muscle-activity sensor role."""

SynchronizedFrameConsumer = Callable[[SynchronizedFrame], None]
"""Invoked with each SynchronizedFrame as it is emitted."""


@dataclass
class _BufferedPacket:
    packet: ValidatedPacket
    reference_timestamp_ms: float
    buffered_at_monotonic: float


class GroupSynchronizer:
    """
    Buffers, matches, and times out packets for exactly one
    synchronization group.

    Purpose
        Fully self-contained per-group state and matching logic. Holds
        no reference to any other group's buffers or state, so
        cross-group matching is structurally unreachable — not merely
        prevented by a runtime check (Decision 022).
    """

    def __init__(
        self,
        group_id: str,
        requires_emg: bool,
        on_frame: SynchronizedFrameConsumer,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Initialize the group synchronizer.

        Args:
            group_id: This group's identifier, stamped onto every frame
                it emits.
            requires_emg: Whether this group has an emg device
                configured this session. When False, every
                primary_motion packet emits immediately as
                NOT_REQUIRED — no buffering, no waiting.
            on_frame: Callback invoked with each emitted
                SynchronizedFrame.
            monotonic_clock: Source of monotonic time for timeout
                bookkeeping. Overridable for deterministic tests.
        """
        self._group_id = group_id
        self._requires_emg = requires_emg
        self._on_frame = on_frame
        self._monotonic_clock = monotonic_clock
        self._clock = ReferenceTimestampResolver()
        self._primary_motion_buffer: List[_BufferedPacket] = []
        self._emg_buffer: List[_BufferedPacket] = []

    def handle(self, role: str, packet: ValidatedPacket) -> None:
        """
        Process one packet already known to belong to this group.

        Args:
            role: Either PRIMARY_MOTION_ROLE or EMG_ROLE.
            packet: The packet to process.
        """
        reference_timestamp_ms = self._clock.resolve(
            device_id=packet.device_id,
            device_timestamp_ms=packet.device_timestamp_ms,
            sequence_number=packet.sequence_number,
            received_at=packet.received_at,
        )
        buffered = _BufferedPacket(
            packet=packet,
            reference_timestamp_ms=reference_timestamp_ms,
            buffered_at_monotonic=self._monotonic_clock(),
        )

        self._sweep()

        if role == PRIMARY_MOTION_ROLE:
            self._handle_primary_motion(buffered)
        elif role == EMG_ROLE:
            self._handle_emg(buffered)
        else:
            raise ValueError(f"Unknown synchronization role: {role!r}")

    def _handle_primary_motion(self, buffered: _BufferedPacket) -> None:
        if not self._requires_emg:
            self._emit(
                reference_timestamp_ms=buffered.reference_timestamp_ms,
                sync_status=SyncStatus.NOT_REQUIRED,
                primary_motion=buffered.packet,
                emg=None,
            )
            return

        match = self._pop_closest_within_tolerance(
            self._emg_buffer, buffered.reference_timestamp_ms
        )
        if match is not None:
            self._emit(
                reference_timestamp_ms=buffered.reference_timestamp_ms,
                sync_status=SyncStatus.MATCHED,
                primary_motion=buffered.packet,
                emg=match.packet,
            )
            return

        self._primary_motion_buffer.append(buffered)

    def _handle_emg(self, buffered: _BufferedPacket) -> None:
        match = self._pop_closest_within_tolerance(
            self._primary_motion_buffer, buffered.reference_timestamp_ms
        )
        if match is not None:
            self._emit(
                reference_timestamp_ms=match.reference_timestamp_ms,
                sync_status=SyncStatus.MATCHED,
                primary_motion=match.packet,
                emg=buffered.packet,
            )
            return

        self._emg_buffer.append(buffered)

    def _pop_closest_within_tolerance(
        self, buffer: List[_BufferedPacket], reference_timestamp_ms: float
    ) -> Optional[_BufferedPacket]:
        best_index: Optional[int] = None
        best_delta: Optional[float] = None
        for index, candidate in enumerate(buffer):
            delta = abs(candidate.reference_timestamp_ms - reference_timestamp_ms)
            if delta > etl_config.SYNC_TOLERANCE_MS:
                continue
            # Buffers are always time-ordered oldest-to-newest (append
            # order), so scanning left-to-right and replacing only on a
            # strictly smaller delta applies the deterministic tie-break
            # policy for free: on an exact tie, the earlier (lower
            # reference_timestamp) candidate is encountered first and
            # is therefore kept.
            if best_delta is None or delta < best_delta:
                best_index = index
                best_delta = delta
        if best_index is None:
            return None
        return buffer.pop(best_index)

    def _sweep(self) -> None:
        now = self._monotonic_clock()
        self._sweep_primary_motion(now)
        self._sweep_emg(now)

    def _sweep_primary_motion(self, now: float) -> None:
        still_pending: List[_BufferedPacket] = []
        for buffered in self._primary_motion_buffer:
            age_ms = (now - buffered.buffered_at_monotonic) * 1000.0
            if age_ms > etl_config.SYNC_TIMEOUT_MS:
                logger.warning(
                    "group_synchronizer.primary_motion_timed_out",
                    extra={
                        "group_id": self._group_id,
                        "device_id": buffered.packet.device_id,
                        "age_ms": age_ms,
                    },
                )
                self._emit(
                    reference_timestamp_ms=buffered.reference_timestamp_ms,
                    sync_status=SyncStatus.TIMED_OUT,
                    primary_motion=buffered.packet,
                    emg=None,
                )
            else:
                still_pending.append(buffered)
        self._primary_motion_buffer = still_pending

    def _sweep_emg(self, now: float) -> None:
        still_pending: List[_BufferedPacket] = []
        for buffered in self._emg_buffer:
            age_ms = (now - buffered.buffered_at_monotonic) * 1000.0
            if age_ms > etl_config.SYNC_TIMEOUT_MS:
                # No primary_motion anchor exists for an orphaned emg
                # packet — logged and dropped, never emitted as a frame.
                logger.warning(
                    "group_synchronizer.emg_orphan_dropped",
                    extra={
                        "group_id": self._group_id,
                        "device_id": buffered.packet.device_id,
                        "age_ms": age_ms,
                    },
                )
            else:
                still_pending.append(buffered)
        self._emg_buffer = still_pending

    def _emit(
        self,
        reference_timestamp_ms: float,
        sync_status: SyncStatus,
        primary_motion: ValidatedPacket,
        emg: Optional[ValidatedPacket],
    ) -> None:
        packets = {PRIMARY_MOTION_ROLE: primary_motion}
        if sync_status != SyncStatus.NOT_REQUIRED:
            packets[EMG_ROLE] = emg

        frame = SynchronizedFrame(
            group_id=self._group_id,
            reference_timestamp=reference_timestamp_ms,
            sync_status=sync_status,
            packets=packets,
        )
        logger.debug(
            "group_synchronizer.frame_emitted",
            extra={"group_id": self._group_id, "sync_status": sync_status.value},
        )
        self._on_frame(frame)
