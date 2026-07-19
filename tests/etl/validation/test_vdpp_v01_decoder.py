"""Unit tests for VDPPv01Decoder.

Uses the independent test encoder in vdpp_v01_helpers.py, never the
production decoder's own internals, to construct fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config import etl_config
from app.etl.receiver import RawPacket
from app.etl.validation.exceptions import PacketDecodeError
from app.etl.validation.rejection import RejectionReason
from app.etl.validation.vdpp_v01 import VDPPv01Decoder

from .vdpp_v01_helpers import (
    DEVICE_IDENTIFIER_SMART_POD,
    encode_emg_band_packet,
    encode_smart_pod_packet,
    encode_vdpp_packet,
)

SMART_POD = etl_config.SMART_POD_DEVICE_ID
EMG_BAND = etl_config.EMG_BAND_DEVICE_ID


def _raw(device_id: str, payload: bytes) -> RawPacket:
    return RawPacket(device_id=device_id, payload=payload, received_at=datetime.now(timezone.utc))


def test_decodes_smart_pod_packet() -> None:
    payload = encode_smart_pod_packet(
        values=(100, -50, 300, 10, -20, 30, 500, 600, 700),
        sequence_number=42,
        device_timestamp_ms=1000,
    )
    decoder = VDPPv01Decoder()

    validated = decoder.decode(_raw(SMART_POD, payload))

    assert validated.device_id == SMART_POD
    assert validated.protocol_version == 1
    assert validated.packet_type == 1
    assert validated.sequence_number == 42
    assert validated.device_timestamp_ms == 1000
    assert dict(validated.raw_channels) == {
        "accel_x": 100,
        "accel_y": -50,
        "accel_z": 300,
        "gyro_x": 10,
        "gyro_y": -20,
        "gyro_z": 30,
        "fsr_1": 500,
        "fsr_2": 600,
        "fsr_3": 700,
    }


def test_decodes_emg_band_packet() -> None:
    payload = encode_emg_band_packet(values=(11, 22))
    decoder = VDPPv01Decoder()

    validated = decoder.decode(_raw(EMG_BAND, payload))

    assert dict(validated.raw_channels) == {
        "quadriceps": 11,
        "hamstring": 22,
    }


def test_rejects_too_short_payload() -> None:
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, b"\x00" * 5))

    assert exc_info.value.reason == RejectionReason.TOO_SHORT


def test_rejects_invalid_magic() -> None:
    payload = bytearray(encode_smart_pod_packet())
    payload[0:2] = b"XX"
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, bytes(payload)))

    assert exc_info.value.reason == RejectionReason.INVALID_MAGIC


def test_rejects_unrecognized_protocol_version() -> None:
    payload = encode_smart_pod_packet(protocol_version=0x02)
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, payload))

    assert exc_info.value.reason == RejectionReason.UNRECOGNIZED_PROTOCOL_VERSION
    assert exc_info.value.protocol_version == 0x02


def test_rejects_unrecognized_packet_type() -> None:
    payload = encode_smart_pod_packet(packet_type=0x09)
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, payload))

    assert exc_info.value.reason == RejectionReason.UNRECOGNIZED_PACKET_TYPE
    assert exc_info.value.packet_type == 0x09


def test_rejects_envelope_length_mismatch() -> None:
    payload = encode_smart_pod_packet() + b"\x00\x00"  # trailing garbage bytes
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, payload))

    assert exc_info.value.reason == RejectionReason.LENGTH_MISMATCH


def test_rejects_declared_payload_length_exceeding_actual_buffer() -> None:
    """A corrupted or malicious header claiming a payload_length far
    larger than the bytes actually present must be rejected safely,
    never cause an out-of-bounds read or a crash.
    """
    payload = bytearray(encode_smart_pod_packet())
    payload[17:19] = (60000).to_bytes(2, "little")  # overwrite payload_length field
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, bytes(payload)))

    assert exc_info.value.reason == RejectionReason.LENGTH_MISMATCH


def test_rejects_checksum_failure() -> None:
    payload = encode_smart_pod_packet(corrupt_crc=True)
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, payload))

    assert exc_info.value.reason == RejectionReason.CHECKSUM_FAILURE


def test_rejects_unrecognized_device_identifier() -> None:
    payload = encode_vdpp_packet(
        device_identifier=0x09,
        payload_values=(1, 2),
        payload_struct_format="<HH",
    )
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, payload))

    assert exc_info.value.reason == RejectionReason.UNRECOGNIZED_DEVICE_IDENTIFIER


def test_rejects_device_identity_mismatch() -> None:
    # Header declares Smart Pod, but the enclosing RawPacket says EMG Band.
    payload = encode_smart_pod_packet()
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(EMG_BAND, payload))

    assert exc_info.value.reason == RejectionReason.DEVICE_IDENTITY_MISMATCH


def test_rejects_payload_not_matching_device_schema_length() -> None:
    # Declares Smart Pod but with an EMG-band-shaped (4-byte) payload.
    payload = encode_vdpp_packet(
        device_identifier=DEVICE_IDENTIFIER_SMART_POD,
        payload_values=(1, 2),
        payload_struct_format="<HH",
    )
    decoder = VDPPv01Decoder()

    with pytest.raises(PacketDecodeError) as exc_info:
        decoder.decode(_raw(SMART_POD, payload))

    assert exc_info.value.reason == RejectionReason.LENGTH_MISMATCH


def test_does_not_mutate_payload_bytes() -> None:
    payload = encode_smart_pod_packet()
    original = bytes(payload)
    decoder = VDPPv01Decoder()

    decoder.decode(_raw(SMART_POD, payload))

    assert payload == original


def test_does_not_reject_physically_extreme_but_structurally_valid_values() -> None:
    """Packet Validation must not encroach on Feature Validation's job:
    a structurally valid packet is never rejected for containing
    physically implausible sensor values.
    """
    payload = encode_smart_pod_packet(
        values=(32767, -32768, 32767, -32768, 32767, -32768, 65535, 65535, 65535)
    )
    decoder = VDPPv01Decoder()

    validated = decoder.decode(_raw(SMART_POD, payload))

    assert validated.raw_channels["accel_x"] == 32767
    assert validated.raw_channels["fsr_1"] == 65535
