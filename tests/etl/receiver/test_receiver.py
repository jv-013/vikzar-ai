"""Unit tests for BLEReceiver, using FakeBLETransport exclusively.

No physical hardware or real BLE library is required to run these tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.config import etl_config
from app.etl.receiver.exceptions import BLEConnectionError
from app.etl.receiver.fake_transport import FakeBLETransport
from app.etl.receiver.packet import RawPacket
from app.etl.receiver.receiver import BLEReceiver

SMART_POD = etl_config.SMART_POD_DEVICE_ID
EMG_BAND = etl_config.EMG_BAND_DEVICE_ID


def _make_receiver(transport: FakeBLETransport) -> tuple[BLEReceiver, list[RawPacket]]:
    received: list[RawPacket] = []
    receiver = BLEReceiver(transport=transport, on_packet=received.append)
    return receiver, received


@pytest.mark.asyncio
async def test_packet_wrapping_preserves_device_id_and_payload() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, received = _make_receiver(transport)

    before = datetime.now(timezone.utc)
    await receiver.start([SMART_POD])
    transport.emit(SMART_POD, b"\x01\x02\x03")
    after = datetime.now(timezone.utc)

    assert len(received) == 1
    packet = received[0]
    assert packet.device_id == SMART_POD
    assert packet.payload == b"\x01\x02\x03"
    assert before <= packet.received_at <= after


@pytest.mark.asyncio
async def test_start_connects_and_stop_disconnects() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, _ = _make_receiver(transport)

    assert not receiver.is_running()

    await receiver.start([SMART_POD])
    assert receiver.is_running()
    assert receiver.is_device_connected(SMART_POD)

    await receiver.stop()
    assert not receiver.is_running()
    assert not receiver.is_device_connected(SMART_POD)


@pytest.mark.asyncio
async def test_stop_without_start_is_a_safe_no_op() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, _ = _make_receiver(transport)

    await receiver.stop()

    assert not receiver.is_running()


@pytest.mark.asyncio
async def test_packets_are_forwarded_in_order() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, received = _make_receiver(transport)
    await receiver.start([SMART_POD])

    for i in range(5):
        transport.emit(SMART_POD, bytes([i]))

    assert [p.payload for p in received] == [bytes([i]) for i in range(5)]


@pytest.mark.asyncio
async def test_multi_device_packets_are_tagged_correctly() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD, EMG_BAND}))
    receiver, received = _make_receiver(transport)
    await receiver.start([SMART_POD, EMG_BAND])

    transport.emit(SMART_POD, b"\xaa")
    transport.emit(EMG_BAND, b"\xbb")
    transport.emit(SMART_POD, b"\xcc")

    smart_pod_packets = [p for p in received if p.device_id == SMART_POD]
    emg_band_packets = [p for p in received if p.device_id == EMG_BAND]

    assert [p.payload for p in smart_pod_packets] == [b"\xaa", b"\xcc"]
    assert [p.payload for p in emg_band_packets] == [b"\xbb"]


@pytest.mark.asyncio
async def test_connection_failure_raises_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(etl_config, "BLE_RECONNECT_BACKOFF_SECONDS", 0.0)
    transport = FakeBLETransport(
        known_device_ids=frozenset({SMART_POD}),
        connect_failures={SMART_POD: etl_config.BLE_RECONNECT_MAX_ATTEMPTS},
    )
    receiver, _ = _make_receiver(transport)

    with pytest.raises(BLEConnectionError):
        await receiver.start([SMART_POD])

    assert not receiver.is_running()


@pytest.mark.asyncio
async def test_connection_succeeds_after_transient_failures_within_retry_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(etl_config, "BLE_RECONNECT_BACKOFF_SECONDS", 0.0)
    transport = FakeBLETransport(
        known_device_ids=frozenset({SMART_POD}),
        connect_failures={SMART_POD: etl_config.BLE_RECONNECT_MAX_ATTEMPTS - 1},
    )
    receiver, _ = _make_receiver(transport)

    await receiver.start([SMART_POD])

    assert receiver.is_running()
    assert receiver.is_device_connected(SMART_POD)


@pytest.mark.asyncio
async def test_unexpected_disconnect_triggers_reconnect() -> None:
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, _ = _make_receiver(transport)
    await receiver.start([SMART_POD])

    transport.simulate_unexpected_disconnect(SMART_POD)
    assert not receiver.is_device_connected(SMART_POD)

    await receiver.wait_for_pending_reconnects()

    assert receiver.is_device_connected(SMART_POD)


@pytest.mark.asyncio
async def test_reconnect_failure_is_logged_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(etl_config, "BLE_RECONNECT_BACKOFF_SECONDS", 0.0)
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, _ = _make_receiver(transport)
    await receiver.start([SMART_POD])

    # Fail every attempt only for the upcoming reconnect, not the initial
    # connect above, which must succeed for this scenario to be meaningful.
    transport.set_connect_failures(SMART_POD, etl_config.BLE_RECONNECT_MAX_ATTEMPTS)
    transport.simulate_unexpected_disconnect(SMART_POD)

    # Reconnect attempts will exhaust and fail; this must not raise or crash
    # the receiver — it is a background task, not a caller-facing operation.
    await receiver.wait_for_pending_reconnects()

    assert not receiver.is_device_connected(SMART_POD)


@pytest.mark.asyncio
async def test_overlapping_unexpected_disconnects_do_not_duplicate_reconnect_task() -> None:
    """A second unexpected-disconnect signal for a device that already has
    a reconnect in flight must not schedule a second, concurrent reconnect
    task — that was Critical finding #1 from the prior review.
    """
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, _ = _make_receiver(transport)
    await receiver.start([SMART_POD])

    transport.simulate_unexpected_disconnect(SMART_POD)
    # No await between the two signals: the first reconnect task has been
    # scheduled but has not yet had a chance to run, so it is still
    # "not done" — exactly the overlapping-signal scenario being guarded
    # against.
    first_task = receiver._pending_reconnects[SMART_POD]

    transport.simulate_unexpected_disconnect(SMART_POD)
    second_task = receiver._pending_reconnects[SMART_POD]

    assert first_task is second_task, (
        "a second unexpected disconnect must not replace an in-flight "
        "reconnect task for the same device"
    )

    await receiver.wait_for_pending_reconnects()
    assert receiver.is_device_connected(SMART_POD)


@pytest.mark.asyncio
async def test_device_can_reconnect_again_after_a_previous_reconnect_completed() -> None:
    """The duplicate-scheduling guard must only block truly overlapping
    signals — a later, independent disconnect must still trigger a fresh
    reconnect once the prior one has fully resolved.
    """
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, _ = _make_receiver(transport)
    await receiver.start([SMART_POD])

    transport.simulate_unexpected_disconnect(SMART_POD)
    await receiver.wait_for_pending_reconnects()
    assert receiver.is_device_connected(SMART_POD)

    transport.simulate_unexpected_disconnect(SMART_POD)
    assert not receiver.is_device_connected(SMART_POD)
    await receiver.wait_for_pending_reconnects()
    assert receiver.is_device_connected(SMART_POD)


@pytest.mark.asyncio
async def test_stop_cancels_pending_reconnect_before_returning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stop() must fully quiesce the receiver: an in-flight reconnect must
    not be able to complete and mutate state after stop() returns. That
    was Critical finding #2 from the prior review.

    A large backoff is configured so that, absent cancellation, stop()
    would have to wait out a long sleep inside the reconnect's retry loop.
    Asserting stop() completes almost immediately proves it actually
    cancels the task rather than merely waiting for it.
    """
    monkeypatch.setattr(etl_config, "BLE_RECONNECT_BACKOFF_SECONDS", 5.0)
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, _ = _make_receiver(transport)
    await receiver.start([SMART_POD])

    # Every reconnect attempt will fail, so the reconnect task will be
    # sitting inside its retry backoff sleep when stop() is called.
    transport.set_connect_failures(SMART_POD, etl_config.BLE_RECONNECT_MAX_ATTEMPTS)
    transport.simulate_unexpected_disconnect(SMART_POD)
    await asyncio.sleep(0)  # let the reconnect task start and reach its first await

    await asyncio.wait_for(receiver.stop(), timeout=1.0)

    assert not receiver.is_running()
    assert not receiver._pending_reconnects

    # The cancelled reconnect task must not resurrect state after stop().
    await asyncio.sleep(0)
    assert not receiver.is_device_connected(SMART_POD)
    assert receiver._pending_reconnects == {}


@pytest.mark.asyncio
async def test_receiver_does_not_interpret_packet_contents() -> None:
    """The receiver forwards arbitrary bytes unchanged — it performs no
    packet validation. That responsibility belongs to the next ETL stage.
    """
    transport = FakeBLETransport(known_device_ids=frozenset({SMART_POD}))
    receiver, received = _make_receiver(transport)
    await receiver.start([SMART_POD])

    garbage = b"\xff\xff\xff\xff\xff\xff\xff\xff"
    transport.emit(SMART_POD, garbage)

    assert received[0].payload == garbage
