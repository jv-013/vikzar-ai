"""
Packet Validation package.

Stage 2 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/VDPP_v0.1.md.

ValidatedPacket and PacketRejection are exported for use elsewhere within
app/etl (e.g. the future Synchronization stage). They must never be
imported outside app/etl.
"""

from .decoder import PacketDecoder
from .exceptions import PacketDecodeError, PacketValidationError
from .packet import ValidatedPacket
from .rejection import PacketRejection, RejectionReason
from .validator import PACKET_ENVELOPE_MAGIC, PacketValidator, ValidatedPacketConsumer
from .vdpp_v01 import (
    PACKET_TYPE_DEVICE_INFO,
    PACKET_TYPE_HEARTBEAT,
    PACKET_TYPE_SENSOR_DATA,
    PROTOCOL_VERSION as VDPP_V01_PROTOCOL_VERSION,
    VDPPv01Decoder,
)

__all__ = [
    "PacketValidator",
    "ValidatedPacketConsumer",
    "PacketDecoder",
    "PACKET_ENVELOPE_MAGIC",
    "ValidatedPacket",
    "PacketRejection",
    "RejectionReason",
    "PacketValidationError",
    "PacketDecodeError",
    "VDPPv01Decoder",
    "VDPP_V01_PROTOCOL_VERSION",
    "PACKET_TYPE_SENSOR_DATA",
    "PACKET_TYPE_HEARTBEAT",
    "PACKET_TYPE_DEVICE_INFO",
]
