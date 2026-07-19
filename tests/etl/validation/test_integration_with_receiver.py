"""Integration tests: BLE Receiver -> Packet Validation.

Uses BLEReceiver and FakeBLETransport exactly as frozen — this module
must not require any change to app/etl/receiver to compose correctly.
"""

from __future__ import annotations

import pytest

from app.config import etl_config
from app.etl.receiver import BLEReceiver, FakeBLETransport
from app.etl.validation import PacketValidator, VDPPv01Decoder
from app.etl.validation.packet import ValidatedPacket
from app.etl.validation.vdpp_v01 import PACKET_TYPE_SENSOR_DATA, PROTOCOL_VERSION

from .vdpp_v01_helpers import encode_smart_pod_packet

SMART_POD = etl_config.SMART_POD_DEVICE_ID


def _make_validator(on_validated):
    return PacketValidator(
        decoders={(PROTOCOL_VERSION, PACKET_TYPE_SENSOR_DATA): VDPPv01Decoder()},
        on_validated=on_validated,
    )


@pytest.mark.asyncio
async def test_valid_packets_flow_from_ble_receiver_through_packet_validation() -> None:
    validated_packets: list[ValidatedPacket] = []
    validator = _make_validator(validated_packets.append)
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver = BLEReceiver(transport=transport, on_packet=validator.handle)

    await receiver.start([SMART_POD])
    transport.emit(SMART_POD, encode_smart_pod_packet(sequence_number=1))
    transport.emit(SMART_POD, encode_smart_pod_packet(sequence_number=2))

    assert len(validated_packets) == 2
    assert [p.sequence_number for p in validated_packets] == [1, 2]
    assert all(p.device_id == SMART_POD for p in validated_packets)


@pytest.mark.asyncio
async def test_corrupted_packet_from_ble_receiver_is_dropped_not_forwarded() -> None:
    validated_packets: list[ValidatedPacket] = []
    validator = _make_validator(validated_packets.append)
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver = BLEReceiver(transport=transport, on_packet=validator.handle)

    await receiver.start([SMART_POD])
    transport.emit(SMART_POD, b"not a valid vdpp packet")

    assert validated_packets == []
    # BLE Receiver itself must be unaffected by the rejection.
    assert receiver.is_running()
    assert receiver.is_device_connected(SMART_POD)


@pytest.mark.asyncio
async def test_mixed_valid_and_corrupted_packets_only_valid_ones_forwarded() -> None:
    validated_packets: list[ValidatedPacket] = []
    validator = _make_validator(validated_packets.append)
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver = BLEReceiver(transport=transport, on_packet=validator.handle)

    await receiver.start([SMART_POD])
    transport.emit(SMART_POD, encode_smart_pod_packet(sequence_number=1))
    transport.emit(SMART_POD, b"garbage")
    transport.emit(SMART_POD, encode_smart_pod_packet(sequence_number=2))

    assert [p.sequence_number for p in validated_packets] == [1, 2]
