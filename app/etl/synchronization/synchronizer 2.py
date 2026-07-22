"""
Synchronization.

Stage 3 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md,
docs/development/SYNCHRONIZATION_DESIGN.md, and
docs/architecture/10_SYSTEM_DECISIONS.md, Decisions 022/023).

Dispatches each ValidatedPacket to its synchronization group by
device_id, then delegates entirely to that group's own GroupSynchronizer.
Contains no protocol-, device-, or group-specific matching logic itself
— groups never share buffers or state, so cross-group matching is
structurally unreachable, not merely prevented by a check.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Sequence

from app.etl.validation import ValidatedPacket

from .config import SynchronizationGroupConfig
from .group_synchronizer import (
    EMG_ROLE,
    PRIMARY_MOTION_ROLE,
    GroupSynchronizer,
    SynchronizedFrameConsumer,
)

logger = logging.getLogger(__name__)


class Synchronizer:
    """
    Resolves each ValidatedPacket's synchronization group and delegates
    to it.

    Purpose
        The only stage that derives synchronization group identity from
        device_id and stamps it explicitly onto its output
        (SynchronizedFrame.group_id), beginning the bilateral
        preservation contract every later ETL stage must honor
        (Decision 022).
    """

    def __init__(
        self,
        groups: Sequence[SynchronizationGroupConfig],
        on_synchronized: SynchronizedFrameConsumer,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Initialize the synchronizer.

        Args:
            groups: The synchronization groups active this session.
                Synchronizer contains no group-specific logic itself —
                every group is handled by an identically-structured
                GroupSynchronizer instance.
            on_synchronized: Callback invoked with each emitted
                SynchronizedFrame, from whichever group produced it.
            monotonic_clock: Source of monotonic time for timeout
                bookkeeping, propagated to every group. Overridable for
                deterministic tests.

        Raises:
            ValueError: If two groups share a group_id, or if a
                device_id is assigned to more than one group.
        """
        self._device_to_group: Dict[str, str] = {}
        self._device_to_role: Dict[str, str] = {}
        self._group_synchronizers: Dict[str, GroupSynchronizer] = {}

        for group in groups:
            if group.group_id in self._group_synchronizers:
                raise ValueError(
                    f"Duplicate synchronization group_id: {group.group_id!r}"
                )

            self._assign_device(group.primary_motion_device_id, group.group_id, PRIMARY_MOTION_ROLE)
            if group.emg_device_id is not None:
                self._assign_device(group.emg_device_id, group.group_id, EMG_ROLE)

            self._group_synchronizers[group.group_id] = GroupSynchronizer(
                group_id=group.group_id,
                requires_emg=group.emg_device_id is not None,
                on_frame=on_synchronized,
                monotonic_clock=monotonic_clock,
            )

    def _assign_device(self, device_id: str, group_id: str, role: str) -> None:
        existing_group = self._device_to_group.get(device_id)
        if existing_group is not None:
            raise ValueError(
                f"device_id {device_id!r} is already assigned to group "
                f"{existing_group!r}; cannot also assign it to group {group_id!r}"
            )
        self._device_to_group[device_id] = group_id
        self._device_to_role[device_id] = role

    def handle(self, packet: ValidatedPacket) -> None:
        """
        Resolve and process a single ValidatedPacket.

        This is the entry point wired as PacketValidator's on_validated
        callback. It never raises — every failure is logged and the
        packet is dropped.

        Args:
            packet: The packet to process.
        """
        try:
            self._handle(packet)
        except Exception:
            logger.exception(
                "synchronizer.unexpected_error",
                extra={"device_id": packet.device_id},
            )

    def _handle(self, packet: ValidatedPacket) -> None:
        group_id = self._device_to_group.get(packet.device_id)
        role = self._device_to_role.get(packet.device_id)

        if group_id is None or role is None:
            logger.warning(
                "synchronizer.unconfigured_device",
                extra={"device_id": packet.device_id},
            )
            return

        self._group_synchronizers[group_id].handle(role, packet)
