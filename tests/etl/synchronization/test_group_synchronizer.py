"""Unit tests for GroupSynchronizer — matching, timeout, and determinism."""

from __future__ import annotations

import logging
from typing import List

import pytest

from app.config import etl_config
from app.etl.synchronization.frame import SyncStatus, SynchronizedFrame
from app.etl.synchronization.group_synchronizer import (
    EMG_ROLE,
    PRIMARY_MOTION_ROLE,
    GroupSynchronizer,
    _BufferedPacket,
)

from .helpers import FakeMonotonicClock, make_validated_packet

TOLERANCE = etl_config.SYNC_TOLERANCE_MS
TIMEOUT = etl_config.SYNC_TIMEOUT_MS


def _make_synchronizer(requires_emg: bool = True, clock: FakeMonotonicClock = None):
    received: List[SynchronizedFrame] = []
    clock = clock or FakeMonotonicClock()
    synchronizer = GroupSynchronizer(
        group_id="left_lower_limb",
        requires_emg=requires_emg,
        on_frame=received.append,
        monotonic_clock=clock,
    )
    return synchronizer, received, clock


def test_primary_motion_then_emg_matches_within_tolerance() -> None:
    synchronizer, received, _ = _make_synchronizer()

    primary = make_validated_packet("device_primary", 1000)
    emg = make_validated_packet("device_emg", 1000 + TOLERANCE - 1)

    synchronizer.handle(PRIMARY_MOTION_ROLE, primary)
    synchronizer.handle(EMG_ROLE, emg)

    assert len(received) == 1
    frame = received[0]
    assert frame.group_id == "left_lower_limb"
    assert frame.sync_status == SyncStatus.MATCHED
    assert frame.reference_timestamp == 1000
    assert frame.packets[PRIMARY_MOTION_ROLE] is primary
    assert frame.packets[EMG_ROLE] is emg


def test_emg_then_primary_motion_also_matches() -> None:
    synchronizer, received, _ = _make_synchronizer()

    emg = make_validated_packet("device_emg", 2000)
    primary = make_validated_packet("device_primary", 2000 + TOLERANCE - 1)

    synchronizer.handle(EMG_ROLE, emg)
    synchronizer.handle(PRIMARY_MOTION_ROLE, primary)

    assert len(received) == 1
    frame = received[0]
    assert frame.sync_status == SyncStatus.MATCHED
    # Reference timestamp is always the primary_motion packet's own time.
    assert frame.reference_timestamp == 2000 + TOLERANCE - 1


def test_delta_exactly_at_tolerance_boundary_matches() -> None:
    """Tolerance is inclusive: a delta exactly equal to sync_tolerance
    must match. Tested against exact float values directly (see the
    tie-break test's docstring for why going through datetime
    round-tripping is the wrong way to test an exact boundary).
    """
    synchronizer, _received, _clock = _make_synchronizer()

    packet = make_validated_packet("device_primary", 1000)
    buffered = _BufferedPacket(
        packet=packet, reference_timestamp_ms=1000.0, buffered_at_monotonic=0.0
    )
    synchronizer._primary_motion_buffer = [buffered]

    match = synchronizer._pop_closest_within_tolerance(
        synchronizer._primary_motion_buffer, reference_timestamp_ms=1000.0 + TOLERANCE
    )

    assert match is buffered


def test_delta_beyond_tolerance_does_not_match() -> None:
    synchronizer, received, _ = _make_synchronizer()

    synchronizer.handle(PRIMARY_MOTION_ROLE, make_validated_packet("device_primary", 1000))
    synchronizer.handle(EMG_ROLE, make_validated_packet("device_emg", 1000 + TOLERANCE + 1))

    assert received == []


def test_closest_candidate_is_chosen_over_a_farther_one() -> None:
    synchronizer, received, _ = _make_synchronizer()

    far = make_validated_packet("device_primary_far", 1000)
    close = make_validated_packet("device_primary_close", 1003)
    synchronizer.handle(PRIMARY_MOTION_ROLE, far)
    synchronizer.handle(PRIMARY_MOTION_ROLE, close)

    emg = make_validated_packet("device_emg", 1004)
    synchronizer.handle(EMG_ROLE, emg)

    assert len(received) == 1
    assert received[0].packets[PRIMARY_MOTION_ROLE] is close


def test_tie_break_chooses_the_earlier_candidate() -> None:
    """Exercises the tie-break rule directly against exact float values.

    Going through the public handle() API for both buffered candidates
    would route the "tie" through datetime.timestamp(), which has
    ~1e-13ms round-trip noise — utterly negligible against a 5ms
    tolerance in production, but enough to turn a deliberately-exact
    tie into a non-tie in a test. Constructing the buffer state directly
    tests the deterministic tie-break policy itself, precisely.
    """
    synchronizer, _received, _clock = _make_synchronizer()

    earlier_packet = make_validated_packet("device_primary_earlier", 997)
    later_packet = make_validated_packet("device_primary_later", 1003)
    earlier = _BufferedPacket(
        packet=earlier_packet, reference_timestamp_ms=997.0, buffered_at_monotonic=0.0
    )
    later = _BufferedPacket(
        packet=later_packet, reference_timestamp_ms=1003.0, buffered_at_monotonic=0.0
    )
    # Buffer order matches real usage: oldest (earlier) appended first.
    synchronizer._primary_motion_buffer = [earlier, later]

    match = synchronizer._pop_closest_within_tolerance(
        synchronizer._primary_motion_buffer, reference_timestamp_ms=1000.0
    )

    assert match is earlier
    assert synchronizer._primary_motion_buffer == [later]


def test_primary_motion_timeout_emits_timed_out_frame(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    clock = FakeMonotonicClock()
    synchronizer, received, clock = _make_synchronizer(clock=clock)

    primary = make_validated_packet("device_primary", 1000)
    synchronizer.handle(PRIMARY_MOTION_ROLE, primary)
    assert received == []

    clock.advance_ms(TIMEOUT + 1)
    # Timeout sweeping is piggybacked on the next arrival, in this group.
    trigger = make_validated_packet("device_primary_2", 5000)
    synchronizer.handle(PRIMARY_MOTION_ROLE, trigger)

    timed_out_frames = [f for f in received if f.sync_status == SyncStatus.TIMED_OUT]
    assert len(timed_out_frames) == 1
    frame = timed_out_frames[0]
    assert frame.packets[PRIMARY_MOTION_ROLE] is primary
    assert frame.packets[EMG_ROLE] is None
    assert any("timed_out" in r.message for r in caplog.records)


def test_emg_timeout_is_dropped_without_a_frame(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    clock = FakeMonotonicClock()
    synchronizer, received, clock = _make_synchronizer(clock=clock)

    emg = make_validated_packet("device_emg", 1000)
    synchronizer.handle(EMG_ROLE, emg)
    assert received == []

    clock.advance_ms(TIMEOUT + 1)
    trigger = make_validated_packet("device_emg_2", 5000)
    synchronizer.handle(EMG_ROLE, trigger)

    # The orphaned emg packet must never produce a frame of its own —
    # there is no primary_motion anchor to build one around.
    assert received == []
    assert any("emg_orphan_dropped" in r.message for r in caplog.records)


def test_not_required_group_emits_immediately_without_buffering() -> None:
    synchronizer, received, _ = _make_synchronizer(requires_emg=False)

    packet = make_validated_packet("device_primary", 1000)
    synchronizer.handle(PRIMARY_MOTION_ROLE, packet)

    assert len(received) == 1
    frame = received[0]
    assert frame.sync_status == SyncStatus.NOT_REQUIRED
    assert frame.packets[PRIMARY_MOTION_ROLE] is packet
    assert EMG_ROLE not in frame.packets


def test_not_required_group_never_waits_even_across_many_packets() -> None:
    synchronizer, received, _ = _make_synchronizer(requires_emg=False)

    for i in range(5):
        synchronizer.handle(PRIMARY_MOTION_ROLE, make_validated_packet(f"device_{i}", 1000 + i))

    assert len(received) == 5
    assert all(f.sync_status == SyncStatus.NOT_REQUIRED for f in received)


def test_multiple_pending_primary_motion_packets_matched_independently() -> None:
    synchronizer, received, _ = _make_synchronizer()

    p1 = make_validated_packet("device_p1", 1000)
    p2 = make_validated_packet("device_p2", 1030)
    synchronizer.handle(PRIMARY_MOTION_ROLE, p1)
    synchronizer.handle(PRIMARY_MOTION_ROLE, p2)
    assert received == []

    e1 = make_validated_packet("device_e1", 1000 + TOLERANCE - 1)
    e2 = make_validated_packet("device_e2", 1030 + TOLERANCE - 1)
    synchronizer.handle(EMG_ROLE, e1)
    synchronizer.handle(EMG_ROLE, e2)

    assert len(received) == 2
    assert received[0].packets[PRIMARY_MOTION_ROLE] is p1
    assert received[0].packets[EMG_ROLE] is e1
    assert received[1].packets[PRIMARY_MOTION_ROLE] is p2
    assert received[1].packets[EMG_ROLE] is e2
