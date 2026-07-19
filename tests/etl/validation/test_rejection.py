"""Unit tests for PacketRejection."""

from __future__ import annotations

import base64

from app.etl.validation.rejection import PacketRejection, RejectionReason


def test_encode_payload_round_trips_arbitrary_bytes() -> None:
    payload = b"\x00\x01\xff\xfe\xde\xad\xbe\xef"

    encoded = PacketRejection.encode_payload(payload)

    assert isinstance(encoded, str)
    assert base64.b64decode(encoded) == payload


def test_encode_payload_handles_empty_bytes() -> None:
    assert base64.b64decode(PacketRejection.encode_payload(b"")) == b""


def test_rejection_reason_values_are_distinct() -> None:
    values = [reason.value for reason in RejectionReason]
    assert len(values) == len(set(values))
