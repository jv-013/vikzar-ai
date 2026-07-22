"""Unit tests for SynchronizedFrame."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from app.etl.synchronization.frame import SyncStatus, SynchronizedFrame

from .helpers import make_validated_packet


def test_stores_fields() -> None:
    packet = make_validated_packet("left_smart_pod", 1000)
    frame = SynchronizedFrame(
        group_id="left_lower_limb",
        reference_timestamp=1000,
        sync_status=SyncStatus.MATCHED,
        packets={"primary_motion": packet},
    )
    assert frame.group_id == "left_lower_limb"
    assert frame.reference_timestamp == 1000
    assert frame.sync_status == SyncStatus.MATCHED
    assert frame.packets["primary_motion"] is packet


def test_packets_is_read_only() -> None:
    packet = make_validated_packet("left_smart_pod", 1000)
    frame = SynchronizedFrame(
        group_id="left_lower_limb",
        reference_timestamp=1000,
        sync_status=SyncStatus.MATCHED,
        packets={"primary_motion": packet},
    )
    assert isinstance(frame.packets, MappingProxyType)
    with pytest.raises(TypeError):
        frame.packets["primary_motion"] = None  # type: ignore[index]


def test_is_immutable() -> None:
    packet = make_validated_packet("left_smart_pod", 1000)
    frame = SynchronizedFrame(
        group_id="left_lower_limb",
        reference_timestamp=1000,
        sync_status=SyncStatus.MATCHED,
        packets={"primary_motion": packet},
    )
    with pytest.raises(FrozenInstanceError):
        frame.group_id = "right_lower_limb"  # type: ignore[misc]


def test_rejects_empty_group_id() -> None:
    packet = make_validated_packet("left_smart_pod", 1000)
    with pytest.raises(ValueError):
        SynchronizedFrame(
            group_id="",
            reference_timestamp=1000,
            sync_status=SyncStatus.MATCHED,
            packets={"primary_motion": packet},
        )


def test_rejects_missing_primary_motion_key() -> None:
    with pytest.raises(ValueError):
        SynchronizedFrame(
            group_id="left_lower_limb",
            reference_timestamp=1000,
            sync_status=SyncStatus.NOT_REQUIRED,
            packets={},
        )


def test_rejects_none_primary_motion_value() -> None:
    with pytest.raises(ValueError):
        SynchronizedFrame(
            group_id="left_lower_limb",
            reference_timestamp=1000,
            sync_status=SyncStatus.TIMED_OUT,
            packets={"primary_motion": None},
        )


def test_not_required_frame_has_no_emg_key() -> None:
    packet = make_validated_packet("left_smart_pod", 1000)
    frame = SynchronizedFrame(
        group_id="left_lower_limb",
        reference_timestamp=1000,
        sync_status=SyncStatus.NOT_REQUIRED,
        packets={"primary_motion": packet},
    )
    assert "emg" not in frame.packets


def test_timed_out_frame_has_none_emg_value() -> None:
    packet = make_validated_packet("left_smart_pod", 1000)
    frame = SynchronizedFrame(
        group_id="left_lower_limb",
        reference_timestamp=1000,
        sync_status=SyncStatus.TIMED_OUT,
        packets={"primary_motion": packet, "emg": None},
    )
    assert frame.packets["emg"] is None
