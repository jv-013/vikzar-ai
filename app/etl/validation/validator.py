"""
Packet Validation.

Stage 2 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/VDPP_v0.1.md).

Dispatches each RawPacket to a registered PacketDecoder by
(protocol_version, packet_type) — never by device_id alone — so future
firmware versions, protocol revisions, and hardware revisions can be
supported by registering new decoders, without changing this module.
Performs no calibration, synchronization, filtering, feature extraction,
or scientific-plausibility checks — those are later ETL stages'
responsibilities.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Dict, Mapping, Optional, Tuple

from app.etl.receiver import RawPacket

from .decoder import PacketDecoder
from .exceptions import PacketDecodeError
from .packet import ValidatedPacket
from .rejection import PacketRejection, RejectionReason

logger = logging.getLogger(__name__)

ValidatedPacketConsumer = Callable[[ValidatedPacket], None]
"""Invoked by PacketValidator with each ValidatedPacket that passes validation."""

PACKET_ENVELOPE_MAGIC: bytes = b"VD"
"""
The stable leading marker every registered protocol's packets begin with.

This is the one part of the wire format Packet Validation itself assumes
directly, so that it can identify a protocol version generically before
dispatching to a version-specific decoder. Every protocol registered with
PacketValidator — VDPP v0.1 and any future revision — is expected to
begin its packets with this marker followed by a protocol version byte
and a packet type byte, specifically so this dispatch layer never needs
to change as protocols evolve. See docs/development/VDPP_v0.1.md,
"Packet Versioning Strategy".
"""

_PROTOCOL_VERSION_OFFSET = 2
_PACKET_TYPE_OFFSET = 3
_MIN_SNIFF_SIZE = 4  # magic(2) + protocol_version(1) + packet_type(1)


class PacketValidator:
    """
    Validates and decodes RawPacket instances into ValidatedPacket.

    Purpose
        Reject structurally invalid or corrupted packets before they can
        reach Synchronization, while preserving enough diagnostic
        information about every rejection to debug it — without ever
        letting the rejected packet itself continue downstream.

    Dispatch
        Decoding is dispatched by (protocol_version, packet_type), read
        from the fixed leading envelope common to every registered
        protocol. Device identity is not part of dispatch — it is a
        concern internal to whichever decoder is selected, so it can
        vary per protocol or device without changing this class.
    """

    def __init__(
        self,
        decoders: Mapping[Tuple[int, int], PacketDecoder],
        on_validated: ValidatedPacketConsumer,
    ) -> None:
        """
        Initialize the validator.

        Args:
            decoders: Registered decoders keyed by
                (protocol_version, packet_type). Packet Validation
                contains no protocol-specific logic itself.
            on_validated: Callback invoked with each successfully
                decoded ValidatedPacket.
        """
        self._decoders: Dict[Tuple[int, int], PacketDecoder] = dict(decoders)
        self._on_validated = on_validated

    def handle(self, raw_packet: RawPacket) -> None:
        """
        Validate and decode a single RawPacket.

        This is the entry point wired as BLEReceiver's on_packet
        callback. It never raises — every failure is logged as a
        PacketRejection and the packet is dropped, never forwarded.

        Args:
            raw_packet: The packet to validate.
        """
        try:
            self._handle(raw_packet)
        except Exception:
            logger.exception(
                "packet_validator.unexpected_error",
                extra={"device_id": raw_packet.device_id},
            )

    def _handle(self, raw_packet: RawPacket) -> None:
        payload = raw_packet.payload

        if len(payload) < _MIN_SNIFF_SIZE:
            self._reject(raw_packet, RejectionReason.TOO_SHORT, None, None)
            return

        if payload[0:2] != PACKET_ENVELOPE_MAGIC:
            self._reject(raw_packet, RejectionReason.INVALID_MAGIC, None, None)
            return

        protocol_version = payload[_PROTOCOL_VERSION_OFFSET]
        packet_type = payload[_PACKET_TYPE_OFFSET]

        decoder = self._decoders.get((protocol_version, packet_type))
        if decoder is None:
            reason = (
                RejectionReason.UNRECOGNIZED_PACKET_TYPE
                if self._is_known_protocol_version(protocol_version)
                else RejectionReason.UNRECOGNIZED_PROTOCOL_VERSION
            )
            self._reject(raw_packet, reason, protocol_version, packet_type)
            return

        try:
            validated = decoder.decode(raw_packet)
        except PacketDecodeError as exc:
            self._reject(
                raw_packet,
                exc.reason,
                exc.protocol_version if exc.protocol_version is not None else protocol_version,
                exc.packet_type if exc.packet_type is not None else packet_type,
            )
            return
        except Exception:
            logger.exception(
                "packet_validator.decoder_raised_unexpectedly",
                extra={"device_id": raw_packet.device_id},
            )
            self._reject(raw_packet, RejectionReason.DECODE_ERROR, protocol_version, packet_type)
            return

        self._on_validated(validated)

    def _is_known_protocol_version(self, protocol_version: int) -> bool:
        return any(version == protocol_version for version, _ in self._decoders)

    def _reject(
        self,
        raw_packet: RawPacket,
        reason: RejectionReason,
        protocol_version: Optional[int],
        packet_type: Optional[int],
    ) -> None:
        rejection = PacketRejection(
            timestamp=datetime.now(timezone.utc),
            device_id=raw_packet.device_id,
            protocol_version=protocol_version,
            packet_type=packet_type,
            reason=reason,
            raw_payload_base64=PacketRejection.encode_payload(raw_packet.payload),
        )
        logger.warning(
            "packet_validator.packet_rejected",
            extra={
                "device_id": rejection.device_id,
                "protocol_version": rejection.protocol_version,
                "packet_type": rejection.packet_type,
                "reason": rejection.reason.value,
                "raw_payload_base64": rejection.raw_payload_base64,
            },
        )
