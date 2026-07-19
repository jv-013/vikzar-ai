"""
Test-only VDPP v0.1 packet encoder.

Builds byte payloads matching docs/development/VDPP_v0.1.md, used only to
construct RawPacket fixtures for decoder tests. Not shipped production
code — mirrors the role FakeBLETransport plays for BLE Receiver tests.

The CRC implementation here is written independently from
app.etl.validation.vdpp_v01's decoder rather than imported, so that
golden-path tests provide real cross-validation of the production CRC
logic instead of the decoder silently validating against its own bugs.
"""

from __future__ import annotations

import struct
from typing import Sequence

MAGIC = b"VD"
PROTOCOL_VERSION = 0x01
PACKET_TYPE_SENSOR_DATA = 0x01
DEVICE_IDENTIFIER_SMART_POD = 0x01
DEVICE_IDENTIFIER_EMG_BAND = 0x02

_HEADER_STRUCT = struct.Struct("<2sBBBIQH")


def crc16_ccitt_false(data: bytes) -> int:
    """Independent CRC-16/CCITT-FALSE implementation for test fixtures."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def encode_vdpp_packet(
    *,
    device_identifier: int,
    payload_values: Sequence[int],
    payload_struct_format: str,
    sequence_number: int = 0,
    device_timestamp_ms: int = 0,
    protocol_version: int = PROTOCOL_VERSION,
    packet_type: int = PACKET_TYPE_SENSOR_DATA,
    corrupt_crc: bool = False,
) -> bytes:
    """Encode a VDPP v0.1 packet from explicit field values."""
    payload = struct.pack(payload_struct_format, *payload_values)
    header = _HEADER_STRUCT.pack(
        MAGIC,
        protocol_version,
        packet_type,
        device_identifier,
        sequence_number,
        device_timestamp_ms,
        len(payload),
    )
    body = header + payload
    crc = crc16_ccitt_false(body)
    if corrupt_crc:
        crc ^= 0xFFFF
    return body + struct.pack("<H", crc)


def encode_smart_pod_packet(
    values: Sequence[int] = (100, -50, 300, 10, -20, 30, 500, 600, 700),
    **kwargs,
) -> bytes:
    """Encode a Vikzar Smart Pod SENSOR_DATA packet."""
    return encode_vdpp_packet(
        device_identifier=DEVICE_IDENTIFIER_SMART_POD,
        payload_values=values,
        payload_struct_format="<hhhhhhHHH",
        **kwargs,
    )


def encode_emg_band_packet(
    values: Sequence[int] = (111, 222),
    **kwargs,
) -> bytes:
    """Encode an EMG Band SENSOR_DATA packet (quadriceps, hamstring)."""
    return encode_vdpp_packet(
        device_identifier=DEVICE_IDENTIFIER_EMG_BAND,
        payload_values=values,
        payload_struct_format="<HH",
        **kwargs,
    )
