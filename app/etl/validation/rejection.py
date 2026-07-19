"""
PacketRejection: structured diagnostic record for a dropped packet.

Purpose
    Preserve enough information to debug why a packet was rejected,
    without ever letting the packet itself continue into downstream ETL
    processing. PacketRejection exists only to be logged — Packet
    Validation must never forward it, retry it, or use it to construct a
    ValidatedPacket.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class RejectionReason(str, Enum):
    """Specific, distinguishable reasons a packet was rejected."""

    TOO_SHORT = "too_short"
    INVALID_MAGIC = "invalid_magic"
    UNRECOGNIZED_PROTOCOL_VERSION = "unrecognized_protocol_version"
    UNRECOGNIZED_PACKET_TYPE = "unrecognized_packet_type"
    UNRECOGNIZED_DEVICE_IDENTIFIER = "unrecognized_device_identifier"
    DEVICE_IDENTITY_MISMATCH = "device_identity_mismatch"
    LENGTH_MISMATCH = "length_mismatch"
    CHECKSUM_FAILURE = "checksum_failure"
    DECODE_ERROR = "decode_error"


@dataclass(frozen=True)
class PacketRejection:
    """
    Diagnostic record for a single rejected packet.

    This record exists only for observability and debugging. It must
    never be used to construct a ValidatedPacket or otherwise continue
    into downstream ETL processing.

    Attributes
        timestamp: When the rejection was recorded.
        device_id: The RawPacket's device_id, as tagged by BLE Receiver.
        protocol_version: The packet's declared protocol version, if it
            could be read before the failure occurred.
        packet_type: The packet's declared packet type, if it could be
            read before the failure occurred.
        reason: The specific validation failure.
        raw_payload_base64: The original raw packet bytes, base64-encoded
            for safe inclusion in structured logs.
    """

    timestamp: datetime
    device_id: str
    protocol_version: Optional[int]
    packet_type: Optional[int]
    reason: RejectionReason
    raw_payload_base64: str

    @staticmethod
    def encode_payload(payload: bytes) -> str:
        """Encode raw packet bytes safely for inclusion in a log record."""
        return base64.b64encode(payload).decode("ascii")
