"""
Synchronization package.

Stage 3 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md,
docs/development/SYNCHRONIZATION_DESIGN.md, and
docs/architecture/10_SYSTEM_DECISIONS.md, Decisions 022/023.

SynchronizedFrame is exported for use elsewhere within app/etl (e.g. the
future Calibration stage). It must never be imported outside app/etl.
"""

from .config import SynchronizationGroupConfig
from .frame import SyncStatus, SynchronizedFrame
from .group_synchronizer import EMG_ROLE, PRIMARY_MOTION_ROLE, SynchronizedFrameConsumer
from .synchronizer import Synchronizer

__all__ = [
    "Synchronizer",
    "SynchronizationGroupConfig",
    "SynchronizedFrame",
    "SyncStatus",
    "SynchronizedFrameConsumer",
    "PRIMARY_MOTION_ROLE",
    "EMG_ROLE",
]
