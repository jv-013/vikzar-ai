"""
VDPP v0.1 decoder.

Implements docs/development/VDPP_v0.1.md — a development-only wire
protocol. No physical device implements it; see that document for the
full packet format specification and rationale.
"""

from __future__ import annotations

import struct
from typing import Dict, Mapping, Tuple

from app.config import etl_config
from app.etl.receiver import RawPacket

from .exceptions import PacketDecodeError
from .packet import ValidatedPacket
from .rejection import RejectionReason
from .validator import PACKET_ENVELOPE_MAGIC

PROTOCOL_VERSION: int = 0x01

PACKET_TYPE_SENSOR_DATA: int = 0x01
PACKET_TYPE_HEARTBEAT: int = 0x02
PACKET_TYPE_DEVICE_INFO: int = 0x03
"""HEARTBEAT and DEVICE_INFO are framed by the spec but not implemented
by this decoder — see VDPP_v0.1.md, "Reserved Bytes for Future
Expansion"."""

_DEVICE_IDENTIFIER_SMART_POD: int = 0x01
_DEVICE_IDENTIFIER_EMG_BAND: int = 0x02

_DEVICE_IDENTIFIER_TO_DEVICE_ID: Dict[int, str] = {
    _DEVICE_IDENTIFIER_SMART_POD: etl_config.SMART_POD_DEVICE_ID,
    _DEVICE_IDENTIFIER_EMG_BAND: etl_config.EMG_BAND_DEVICE_ID,
}

_HEADER_STRUCT = struct.Struct("<2sBBBIQH")
# magic(2s) version(B) packet_type(B) device_identifier(B)
# sequence_number(I) device_timestamp_ms(Q) payload_length(H)
_HEADER_SIZE = _HEADER_STRUCT.size  # 19
_CRC_SIZE = 2
_MIN_PACKET_SIZE = _HEADER_SIZE + _CRC_SIZE  # 21
_CRC_STRUCT = struct.Struct("<H")

_SMART_POD_PAYLOAD_STRUCT = struct.Struct("<hhhhhhHHH")
_SMART_POD_CHANNEL_NAMES: Tuple[str, ...] = (
    "accel_x", "accel_y", "accel_z",
    "gyro_x", "gyro_y", "gyro_z",
    # Indexed rather than anatomically named (e.g. "fsr_heel"): the Smart
    # Pod is a mount-agnostic hardware module (shin guard, compression
    # sleeve, knee brace, or future wearable), so ETL must not bake in an
    # assumption about which body region an FSR channel corresponds to.
    # That mapping is deployment metadata, resolved outside ETL.
    "fsr_1", "fsr_2", "fsr_3",
)

_EMG_BAND_PAYLOAD_STRUCT = struct.Struct("<HH")
_EMG_BAND_CHANNEL_NAMES: Tuple[str, ...] = (
    # Anatomical only, never left/right: each EMG Band belongs to exactly
    # one synchronization group (Decision 022), so limb identity is
    # already carried by group_id. Encoding it again here would duplicate
    # identity information and make the payload non-reusable across
    # groups. See Decision 024.
    "quadriceps", "hamstring",
)

_DEVICE_IDENTIFIER_TO_SCHEMA: Dict[int, Tuple[struct.Struct, Tuple[str, ...]]] = {
    _DEVICE_IDENTIFIER_SMART_POD: (_SMART_POD_PAYLOAD_STRUCT, _SMART_POD_CHANNEL_NAMES),
    _DEVICE_IDENTIFIER_EMG_BAND: (_EMG_BAND_PAYLOAD_STRUCT, _EMG_BAND_CHANNEL_NAMES),
}


def _crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection/XOR-out)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


class VDPPv01Decoder:
    """
    Decodes VDPP v0.1 SENSOR_DATA packets (Vikzar Smart Pod and EMG Band).

    See docs/development/VDPP_v0.1.md for the full specification. Every
    structural or integrity failure raises PacketDecodeError with a
    specific RejectionReason; nothing is ever silently repaired or
    guessed at.
    """

    def decode(self, raw_packet: RawPacket) -> ValidatedPacket:
        """
        Decode one VDPP v0.1 SENSOR_DATA packet.

        Args:
            raw_packet: The packet to decode. Not mutated.

        Returns:
            The decoded ValidatedPacket.

        Raises:
            PacketDecodeError: On any structural or integrity failure.
        """
        payload = raw_packet.payload

        if len(payload) < _MIN_PACKET_SIZE:
            raise PacketDecodeError(RejectionReason.TOO_SHORT)

        (
            magic,
            version,
            packet_type,
            device_identifier,
            sequence_number,
            device_timestamp_ms,
            payload_length,
        ) = _HEADER_STRUCT.unpack_from(payload, 0)

        # PacketValidator already checks the envelope magic before ever
        # dispatching to a decoder, so this can only fail here if decode()
        # is called directly, bypassing PacketValidator (as the decoder-
        # level unit tests do). Re-checking is deliberate defensive
        # programming — this decoder must stay correct and self-contained
        # on its own, not merely as a component that happens to be safe
        # only when invoked through PacketValidator's dispatch path.
        if magic != PACKET_ENVELOPE_MAGIC:
            raise PacketDecodeError(RejectionReason.INVALID_MAGIC)

        if version != PROTOCOL_VERSION:
            raise PacketDecodeError(
                RejectionReason.UNRECOGNIZED_PROTOCOL_VERSION, protocol_version=version
            )

        if packet_type != PACKET_TYPE_SENSOR_DATA:
            raise PacketDecodeError(
                RejectionReason.UNRECOGNIZED_PACKET_TYPE,
                protocol_version=version,
                packet_type=packet_type,
            )

        expected_total_length = _HEADER_SIZE + payload_length + _CRC_SIZE
        if len(payload) != expected_total_length:
            raise PacketDecodeError(
                RejectionReason.LENGTH_MISMATCH,
                protocol_version=version,
                packet_type=packet_type,
            )

        crc_offset = _HEADER_SIZE + payload_length
        (received_crc,) = _CRC_STRUCT.unpack_from(payload, crc_offset)
        computed_crc = _crc16_ccitt_false(payload[:crc_offset])
        if received_crc != computed_crc:
            raise PacketDecodeError(
                RejectionReason.CHECKSUM_FAILURE,
                protocol_version=version,
                packet_type=packet_type,
            )

        expected_device_id = _DEVICE_IDENTIFIER_TO_DEVICE_ID.get(device_identifier)
        if expected_device_id is None:
            raise PacketDecodeError(
                RejectionReason.UNRECOGNIZED_DEVICE_IDENTIFIER,
                protocol_version=version,
                packet_type=packet_type,
            )
        if expected_device_id != raw_packet.device_id:
            raise PacketDecodeError(
                RejectionReason.DEVICE_IDENTITY_MISMATCH,
                protocol_version=version,
                packet_type=packet_type,
            )

        sensor_payload = payload[_HEADER_SIZE:crc_offset]
        raw_channels = self._decode_sensor_payload(
            device_identifier, sensor_payload, version, packet_type
        )

        return ValidatedPacket(
            device_id=raw_packet.device_id,
            received_at=raw_packet.received_at,
            protocol_version=version,
            packet_type=packet_type,
            sequence_number=sequence_number,
            device_timestamp_ms=device_timestamp_ms,
            raw_channels=raw_channels,
        )

    def _decode_sensor_payload(
        self,
        device_identifier: int,
        sensor_payload: bytes,
        version: int,
        packet_type: int,
    ) -> Mapping[str, int]:
        payload_struct, channel_names = _DEVICE_IDENTIFIER_TO_SCHEMA[device_identifier]

        if len(sensor_payload) != payload_struct.size:
            raise PacketDecodeError(
                RejectionReason.LENGTH_MISMATCH,
                protocol_version=version,
                packet_type=packet_type,
            )

        try:
            values = payload_struct.unpack(sensor_payload)
        except struct.error as exc:
            raise PacketDecodeError(
                RejectionReason.DECODE_ERROR,
                protocol_version=version,
                packet_type=packet_type,
            ) from exc

        return dict(zip(channel_names, values))
