"""Unit tests for PacketValidator's dispatch and diagnostic-logging behavior."""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import List, Optional

import pytest

from app.config import etl_config
from app.etl.receiver import RawPacket
from app.etl.validation.exceptions import PacketDecodeError
from app.etl.validation.packet import ValidatedPacket
from app.etl.validation.rejection import RejectionReason
from app.etl.validation.validator import PacketValidator

from .vdpp_v01_helpers import encode_smart_pod_packet

SMART_POD = etl_config.SMART_POD_DEVICE_ID


def _raw(payload: bytes, device_id: str = SMART_POD) -> RawPacket:
    return RawPacket(device_id=device_id, payload=payload, received_at=datetime.now(timezone.utc))


def _make_validated(device_id: str = SMART_POD) -> ValidatedPacket:
    return ValidatedPacket(
        device_id=device_id,
        received_at=datetime.now(timezone.utc),
        protocol_version=1,
        packet_type=1,
        sequence_number=0,
        device_timestamp_ms=0,
        raw_channels={"x": 1},
    )


class _StubDecoder:
    """A minimal PacketDecoder test double."""

    def __init__(
        self,
        result: Optional[ValidatedPacket] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self._result = result
        self._error = error
        self.calls: List[RawPacket] = []

    def decode(self, raw_packet: RawPacket) -> ValidatedPacket:
        self.calls.append(raw_packet)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


def _rejection_records(caplog: pytest.LogCaptureFixture) -> List[logging.LogRecord]:
    return [r for r in caplog.records if hasattr(r, "reason")]


def test_successful_decode_forwards_to_on_validated() -> None:
    validated = _make_validated()
    decoder = _StubDecoder(result=validated)
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={(1, 1): decoder}, on_validated=received.append)

    validator.handle(_raw(encode_smart_pod_packet()))

    assert received == [validated]
    assert len(decoder.calls) == 1


def test_too_short_payload_never_reaches_a_decoder(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    decoder = _StubDecoder()
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={(1, 1): decoder}, on_validated=received.append)

    validator.handle(_raw(b"\x01\x02"))

    assert received == []
    assert decoder.calls == []
    record = _rejection_records(caplog)[-1]
    assert record.reason == RejectionReason.TOO_SHORT.value
    assert record.protocol_version is None
    assert record.packet_type is None


def test_invalid_magic_never_reaches_a_decoder(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    decoder = _StubDecoder()
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={(1, 1): decoder}, on_validated=received.append)

    payload = bytearray(encode_smart_pod_packet())
    payload[0:2] = b"XX"
    validator.handle(_raw(bytes(payload)))

    assert received == []
    assert decoder.calls == []
    record = _rejection_records(caplog)[-1]
    assert record.reason == RejectionReason.INVALID_MAGIC.value


def test_unrecognized_protocol_version_is_distinguished(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={(1, 1): _StubDecoder()}, on_validated=received.append)

    payload = encode_smart_pod_packet(protocol_version=0x02)
    validator.handle(_raw(payload))

    assert received == []
    record = _rejection_records(caplog)[-1]
    assert record.reason == RejectionReason.UNRECOGNIZED_PROTOCOL_VERSION.value
    assert record.protocol_version == 0x02
    assert record.device_id == SMART_POD


def test_known_version_unknown_type_is_distinguished_from_unknown_version(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A registered protocol version with an unregistered packet type must
    be reported distinctly from an entirely unknown protocol version —
    the refinement this dispatch design exists to support.
    """
    caplog.set_level(logging.WARNING)
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={(1, 1): _StubDecoder()}, on_validated=received.append)

    payload = encode_smart_pod_packet(packet_type=0x09)
    validator.handle(_raw(payload))

    assert received == []
    record = _rejection_records(caplog)[-1]
    assert record.reason == RejectionReason.UNRECOGNIZED_PACKET_TYPE.value
    assert record.protocol_version == 1
    assert record.packet_type == 0x09


def test_multiple_packet_types_under_same_protocol_version_dispatch_independently() -> None:
    decoder_type_1 = _StubDecoder(result=_make_validated())
    decoder_type_2 = _StubDecoder(result=_make_validated())
    received: List[ValidatedPacket] = []
    validator = PacketValidator(
        decoders={(1, 1): decoder_type_1, (1, 2): decoder_type_2},
        on_validated=received.append,
    )

    validator.handle(_raw(encode_smart_pod_packet(packet_type=1)))
    validator.handle(_raw(encode_smart_pod_packet(packet_type=2)))

    assert len(decoder_type_1.calls) == 1
    assert len(decoder_type_2.calls) == 1
    assert len(received) == 2


def test_decoder_decode_error_is_rejected_with_its_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    error = PacketDecodeError(RejectionReason.CHECKSUM_FAILURE, protocol_version=1, packet_type=1)
    decoder = _StubDecoder(error=error)
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={(1, 1): decoder}, on_validated=received.append)

    validator.handle(_raw(encode_smart_pod_packet()))

    assert received == []
    record = _rejection_records(caplog)[-1]
    assert record.reason == RejectionReason.CHECKSUM_FAILURE.value


def test_decoder_raising_unexpected_exception_is_contained(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug inside a decoder must never propagate out of PacketValidator —
    Packet Validation is the last line of defense before BLE Receiver's
    notification-delivery path, which has no exception handling of its
    own around this callback.
    """
    caplog.set_level(logging.WARNING)
    decoder = _StubDecoder(error=RuntimeError("decoder bug"))
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={(1, 1): decoder}, on_validated=received.append)

    validator.handle(_raw(encode_smart_pod_packet()))  # must not raise

    assert received == []
    reasons = [r.reason for r in _rejection_records(caplog)]
    assert RejectionReason.DECODE_ERROR.value in reasons


def test_handle_never_raises_even_on_internal_bug() -> None:
    class ExplodingDecoder:
        def decode(self, raw_packet: RawPacket) -> ValidatedPacket:
            raise RuntimeError("boom")

    validator = PacketValidator(decoders={(1, 1): ExplodingDecoder()}, on_validated=lambda p: None)

    validator.handle(_raw(encode_smart_pod_packet()))  # must not raise


def test_rejection_diagnostic_contains_full_required_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every field the approved design requires: timestamp (implicit via
    log record), device identifier, protocol version, packet type,
    reason, and safely-encoded original raw bytes.
    """
    caplog.set_level(logging.WARNING)
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={}, on_validated=received.append)

    payload = b"VD" + bytes([0x05, 0x01])  # valid envelope, unknown version
    validator.handle(_raw(payload))

    record = _rejection_records(caplog)[-1]
    assert record.device_id == SMART_POD
    assert record.protocol_version == 0x05
    assert record.packet_type == 0x01
    assert record.reason == RejectionReason.UNRECOGNIZED_PROTOCOL_VERSION.value
    assert base64.b64decode(record.raw_payload_base64) == payload
    assert received == []


def test_rejected_packets_never_reach_on_validated() -> None:
    """The refinement's core requirement: diagnostic records exist only
    for observability and must never continue into downstream processing.
    """
    received: List[ValidatedPacket] = []
    validator = PacketValidator(decoders={}, on_validated=received.append)

    for payload in (b"\x00", b"VDxx", encode_smart_pod_packet(corrupt_crc=True)):
        validator.handle(_raw(payload))

    assert received == []
