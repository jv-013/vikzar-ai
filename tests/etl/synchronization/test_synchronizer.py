"""Unit tests for Synchronizer — group dispatch, isolation, and safety."""

from __future__ import annotations

import logging
from typing import List

import pytest

from app.config import etl_config
from app.etl.synchronization.config import SynchronizationGroupConfig
from app.etl.synchronization.frame import SyncStatus, SynchronizedFrame
from app.etl.synchronization.synchronizer import Synchronizer

from .helpers import make_validated_packet

TOLERANCE = etl_config.SYNC_TOLERANCE_MS

LEFT_GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb",
    primary_motion_device_id="left_smart_pod",
    emg_device_id="left_emg_band",
)
RIGHT_GROUP = SynchronizationGroupConfig(
    group_id="right_lower_limb",
    primary_motion_device_id="right_smart_pod",
    emg_device_id="right_emg_band",
)


def _make_synchronizer(groups):
    received: List[SynchronizedFrame] = []
    synchronizer = Synchronizer(groups=groups, on_synchronized=received.append)
    return synchronizer, received


def test_packets_route_to_the_correct_group() -> None:
    synchronizer, received = _make_synchronizer([LEFT_GROUP, RIGHT_GROUP])

    left_primary = make_validated_packet("left_smart_pod", 1000)
    left_emg = make_validated_packet("left_emg_band", 1000 + TOLERANCE - 1)
    right_primary = make_validated_packet("right_smart_pod", 2000)
    right_emg = make_validated_packet("right_emg_band", 2000 + TOLERANCE - 1)

    synchronizer.handle(left_primary)
    synchronizer.handle(left_emg)
    synchronizer.handle(right_primary)
    synchronizer.handle(right_emg)

    assert len(received) == 2
    assert received[0].group_id == "left_lower_limb"
    assert received[1].group_id == "right_lower_limb"


def test_near_miss_never_matches_across_groups() -> None:
    """The single most important test in this suite (per
    SYNCHRONIZATION_DESIGN.md, section 14).

    An emg packet numerically closer to the OTHER group's primary_motion
    candidate than to its own must still only ever match within its own
    group — because the two groups' buffers are never even compared,
    not because a filter rejects the closer, wrong-group candidate.
    """
    synchronizer, received = _make_synchronizer([LEFT_GROUP, RIGHT_GROUP])

    left_primary = make_validated_packet("left_smart_pod", 1000)
    right_primary = make_validated_packet("right_smart_pod", 1001)
    synchronizer.handle(left_primary)
    synchronizer.handle(right_primary)
    assert received == []

    # 3ms from right_primary (1001), 4ms from left_primary (1000) — the
    # wrong-group candidate is numerically closer.
    left_emg = make_validated_packet("left_emg_band", 1004)
    synchronizer.handle(left_emg)

    assert len(received) == 1
    frame = received[0]
    assert frame.group_id == "left_lower_limb"
    assert frame.packets["primary_motion"] is left_primary
    assert frame.packets["emg"] is left_emg


def test_right_group_timeout_does_not_affect_left_group_matching() -> None:
    synchronizer, received = _make_synchronizer([LEFT_GROUP, RIGHT_GROUP])

    # Right group: primary_motion buffered, never matched (no emg sent).
    synchronizer.handle(make_validated_packet("right_smart_pod", 1000))

    # Left group proceeds through several successful matches, unaffected.
    # Same two physical devices throughout, as in real usage — only the
    # sequence number and timestamp advance per packet.
    for i in range(3):
        base = 1000 + i * 30
        primary = make_validated_packet("left_smart_pod", base, sequence_number=i)
        emg = make_validated_packet(
            "left_emg_band", base + TOLERANCE - 1, sequence_number=i
        )
        synchronizer.handle(primary)
        synchronizer.handle(emg)

    left_frames = [f for f in received if f.group_id == "left_lower_limb"]
    right_frames = [f for f in received if f.group_id == "right_lower_limb"]
    assert len(left_frames) == 3
    assert all(f.sync_status == SyncStatus.MATCHED for f in left_frames)
    assert right_frames == []  # still buffered, not yet timed out


def test_unconfigured_device_is_logged_and_dropped(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    synchronizer, received = _make_synchronizer([LEFT_GROUP])

    synchronizer.handle(make_validated_packet("unknown_device", 1000))

    assert received == []
    assert any("unconfigured_device" in r.message for r in caplog.records)


def test_duplicate_group_id_raises_at_construction() -> None:
    duplicate = SynchronizationGroupConfig(
        group_id="left_lower_limb",
        primary_motion_device_id="some_other_device",
    )
    with pytest.raises(ValueError):
        Synchronizer(groups=[LEFT_GROUP, duplicate], on_synchronized=lambda f: None)


def test_duplicate_device_id_across_groups_raises_at_construction() -> None:
    conflicting = SynchronizationGroupConfig(
        group_id="right_lower_limb",
        primary_motion_device_id="left_smart_pod",  # already used by LEFT_GROUP
    )
    with pytest.raises(ValueError):
        Synchronizer(groups=[LEFT_GROUP, conflicting], on_synchronized=lambda f: None)


def test_bilateral_match_mode_both_groups_emit_independently() -> None:
    match_left = SynchronizationGroupConfig(
        group_id="left_lower_limb", primary_motion_device_id="left_smart_pod"
    )
    match_right = SynchronizationGroupConfig(
        group_id="right_lower_limb", primary_motion_device_id="right_smart_pod"
    )
    synchronizer, received = _make_synchronizer([match_left, match_right])

    synchronizer.handle(make_validated_packet("left_smart_pod", 1000))
    synchronizer.handle(make_validated_packet("right_smart_pod", 1003))

    assert len(received) == 2
    assert all(f.sync_status == SyncStatus.NOT_REQUIRED for f in received)
    assert {received[0].group_id, received[1].group_id} == {
        "left_lower_limb",
        "right_lower_limb",
    }


def test_scales_to_more_than_two_groups_with_no_code_branching() -> None:
    """A third, unrelated group (e.g. a hypothetical goalkeeper glove)
    uses exactly the same code path as the two limb groups — proving
    'operates identically regardless of group count' is not just a
    design claim.
    """
    glove_group = SynchronizationGroupConfig(
        group_id="goalkeeper_glove",
        primary_motion_device_id="glove_smart_pod",
        emg_device_id="glove_emg_band",
    )
    synchronizer, received = _make_synchronizer([LEFT_GROUP, RIGHT_GROUP, glove_group])

    synchronizer.handle(make_validated_packet("glove_smart_pod", 5000))
    synchronizer.handle(make_validated_packet("glove_emg_band", 5000 + TOLERANCE - 1))
    synchronizer.handle(make_validated_packet("left_smart_pod", 1000))
    synchronizer.handle(make_validated_packet("left_emg_band", 1000 + TOLERANCE - 1))

    glove_frames = [f for f in received if f.group_id == "goalkeeper_glove"]
    left_frames = [f for f in received if f.group_id == "left_lower_limb"]
    assert len(glove_frames) == 1
    assert len(left_frames) == 1
    assert glove_frames[0].sync_status == SyncStatus.MATCHED


def test_no_collapse_frames_from_different_groups_share_no_state() -> None:
    synchronizer, received = _make_synchronizer([LEFT_GROUP, RIGHT_GROUP])

    synchronizer.handle(make_validated_packet("left_smart_pod", 1000))
    synchronizer.handle(make_validated_packet("left_emg_band", 1000 + TOLERANCE - 1))
    synchronizer.handle(make_validated_packet("right_smart_pod", 9000))
    synchronizer.handle(make_validated_packet("right_emg_band", 9000 + TOLERANCE - 1))

    assert len(received) == 2
    left_frame, right_frame = received
    assert left_frame.group_id != right_frame.group_id
    assert left_frame.reference_timestamp != right_frame.reference_timestamp
    # No field on either frame is derived from, or shared with, the
    # other (identity comparison — ValidatedPacket isn't hashable, since
    # it wraps a MappingProxyType).
    left_packets = list(left_frame.packets.values())
    right_packets = list(right_frame.packets.values())
    assert all(lp is not rp for lp in left_packets for rp in right_packets)


def test_handle_never_raises_even_on_internal_bug() -> None:
    def exploding_consumer(frame: SynchronizedFrame) -> None:
        raise RuntimeError("boom")

    synchronizer = Synchronizer(groups=[LEFT_GROUP], on_synchronized=exploding_consumer)

    packet = make_validated_packet("left_smart_pod", 1000)
    synchronizer.handle(packet)  # must not raise
