"""
SynchronizationGroupConfig: the data model for one synchronization group.

See docs/development/SYNCHRONIZATION_DESIGN.md and
docs/architecture/10_SYSTEM_DECISIONS.md, Decision 022.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SynchronizationGroupConfig:
    """
    Describes one independent synchronization group.

    Purpose
        Name which devices belong together (e.g. one side of the
        athlete) without the matching algorithm ever needing to know
        what "left" or "right" — or any other group identity — means.
        `group_id` is an opaque lookup key throughout Synchronization.

    Attributes
        group_id: Free-form identifier for this group (e.g.
            "left_lower_limb"). Never branched on by the algorithm.
        primary_motion_device_id: Logical device id of this group's
            mandatory motion/kinetic sensor. Every group has exactly
            one.
        emg_device_id: Logical device id of this group's optional EMG
            sensor. `None` when this group has no EMG requirement this
            session (e.g. Match Mode).

    Raises
        ValueError: If group_id or primary_motion_device_id is empty.
    """

    group_id: str
    primary_motion_device_id: str
    emg_device_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("SynchronizationGroupConfig.group_id must not be empty.")
        if not self.primary_motion_device_id:
            raise ValueError(
                "SynchronizationGroupConfig.primary_motion_device_id must not be empty."
            )
