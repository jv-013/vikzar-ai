"""Integration test: BLE Receiver -> Packet Validation -> Synchronization.

Uses BLEReceiver, FakeBLETransport, PacketValidator, and VDPPv01Decoder
exactly as frozen — this module requires no change to either upstream
stage to compose correctly.

Scope note: this exercises a single synchronization group, using the
existing singular SMART_POD_DEVICE_ID / EMG_BAND_DEVICE_ID constants,
which VDPPv01Decoder already recognizes today. A true bilateral (two
group, four device) integration test through real VDPP decoding is
blocked by the Packet Validation device-identity cross-check dependency
flagged in SYNCHRONIZATION_DESIGN.md ("Prerequisite") — that stage is
frozen and explicitly out of scope here. Synchronization's own bilateral
correctness (the near-miss cross-group test) is fully covered against
directly-constructed ValidatedPacket fixtures in test_synchronizer.py.
"""

from __future__ import annotations

from typing import List

import pytest

from app.config import etl_config
from app.etl.receiver import BLEReceiver, FakeBLETransport
from app.etl.synchronization import SynchronizationGroupConfig, SynchronizedFrame, Synchronizer
from app.etl.synchronization.frame import SyncStatus
from app.etl.validation import PacketValidator, VDPPv01Decoder
from app.etl.validation.vdpp_v01 import PACKET_TYPE_SENSOR_DATA, PROTOCOL_VERSION

from ..validation.vdpp_v01_helpers import encode_emg_band_packet, encode_smart_pod_packet

SMART_POD = etl_config.SMART_POD_DEVICE_ID
EMG_BAND = etl_config.EMG_BAND_DEVICE_ID

SINGLE_GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb",
    primary_motion_device_id=SMART_POD,
    emg_device_id=EMG_BAND,
)


def _build_pipeline(on_synchronized):
    synchronizer = Synchronizer(groups=[SINGLE_GROUP], on_synchronized=on_synchronized)
    validator = PacketValidator(
        decoders={(PROTOCOL_VERSION, PACKET_TYPE_SENSOR_DATA): VDPPv01Decoder()},
        on_validated=synchronizer.handle,
    )
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD, EMG_BAND}))
    receiver = BLEReceiver(transport=transport, on_packet=validator.handle)
    return receiver, transport


@pytest.mark.asyncio
async def test_matched_frame_flows_through_the_full_pipeline() -> None:
    frames: List[SynchronizedFrame] = []
    receiver, transport = _build_pipeline(frames.append)

    await receiver.start([SMART_POD, EMG_BAND])
    transport.emit(SMART_POD, encode_smart_pod_packet(sequence_number=1))
    transport.emit(EMG_BAND, encode_emg_band_packet(sequence_number=1))

    assert len(frames) == 1
    frame = frames[0]
    assert frame.group_id == "left_lower_limb"
    assert frame.sync_status == SyncStatus.MATCHED
    assert frame.packets["primary_motion"].device_id == SMART_POD
    assert frame.packets["emg"].device_id == EMG_BAND


@pytest.mark.asyncio
async def test_corrupted_packet_never_reaches_synchronization() -> None:
    frames: List[SynchronizedFrame] = []
    receiver, transport = _build_pipeline(frames.append)

    await receiver.start([SMART_POD, EMG_BAND])
    transport.emit(SMART_POD, b"not a valid vdpp packet")

    assert frames == []
    assert receiver.is_running()
