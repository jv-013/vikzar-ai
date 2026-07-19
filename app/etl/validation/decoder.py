"""
PacketDecoder: the abstraction Packet Validation dispatches decoding to.

Packet Validation itself contains no protocol- or device-specific parsing
logic. It only identifies a packet's protocol version and packet type,
then hands the RawPacket to whichever PacketDecoder is registered for
that (protocol_version, packet_type) pair. This is what lets future
firmware versions, protocol revisions, and hardware revisions coexist:
only a new decoder implementation is added or registered — Packet
Validation itself never changes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.etl.receiver import RawPacket

from .packet import ValidatedPacket


@runtime_checkable
class PacketDecoder(Protocol):
    """
    Decodes one specific (protocol version, packet type) combination.

    Implementations own all knowledge of their protocol's byte layout,
    including any further dispatch needed within that protocol (e.g. VDPP
    v0.1 additionally dispatches internally on Device Identifier to
    select a sensor-specific payload schema — see
    docs/development/VDPP_v0.1.md).
    """

    def decode(self, raw_packet: RawPacket) -> ValidatedPacket:
        """
        Decode a RawPacket into a ValidatedPacket.

        Args:
            raw_packet: The packet to decode. Implementations must not
                mutate raw_packet.payload.

        Returns:
            The decoded ValidatedPacket.

        Raises:
            PacketDecodeError: If the packet fails any structural or
                integrity check specific to this protocol/type.
        """
        ...
