"""
BLE Receiver package.

Stage 1 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md
and docs/architecture/01_VIKZAR_ARCHITECTURE_V1.md.

RawPacket is exported for use elsewhere within app/etl (e.g. the future
Packet Validation stage). It must never be imported outside app/etl.
"""

from .exceptions import BLEConnectionError, BLEDeviceNotFoundError, BLEReceiverError
from .fake_transport import FakeBLETransport
from .packet import RawPacket
from .receiver import BLEReceiver, PacketConsumer
from .transport import BLETransport, DisconnectCallback, PacketCallback

__all__ = [
    "BLEReceiver",
    "PacketConsumer",
    "BLETransport",
    "PacketCallback",
    "DisconnectCallback",
    "FakeBLETransport",
    "RawPacket",
    "BLEReceiverError",
    "BLEConnectionError",
    "BLEDeviceNotFoundError",
]
