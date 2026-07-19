"""
Exceptions raised by Packet Validation.
"""

from __future__ import annotations

from typing import Optional

from .rejection import RejectionReason


class PacketValidationError(Exception):
    """Base class for all Packet Validation errors."""


class PacketDecodeError(PacketValidationError):
    """
    Raised by a PacketDecoder when a packet cannot be decoded.

    Carries the specific RejectionReason and, when known, the protocol
    version and packet type read before the failure occurred, so the
    caller can build an accurate diagnostic record without re-parsing.
    """

    def __init__(
        self,
        reason: RejectionReason,
        protocol_version: Optional[int] = None,
        packet_type: Optional[int] = None,
    ) -> None:
        super().__init__(reason.value)
        self.reason = reason
        self.protocol_version = protocol_version
        self.packet_type = packet_type
