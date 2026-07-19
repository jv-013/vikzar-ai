"""Unit tests for SynchronizationGroupConfig."""

from __future__ import annotations

import pytest

from app.etl.synchronization.config import SynchronizationGroupConfig


def test_stores_fields() -> None:
    group = SynchronizationGroupConfig(
        group_id="left_lower_limb",
        primary_motion_device_id="left_smart_pod",
        emg_device_id="left_emg_band",
    )
    assert group.group_id == "left_lower_limb"
    assert group.primary_motion_device_id == "left_smart_pod"
    assert group.emg_device_id == "left_emg_band"


def test_emg_device_id_defaults_to_none() -> None:
    group = SynchronizationGroupConfig(
        group_id="left_lower_limb",
        primary_motion_device_id="left_smart_pod",
    )
    assert group.emg_device_id is None


def test_rejects_empty_group_id() -> None:
    with pytest.raises(ValueError):
        SynchronizationGroupConfig(group_id="", primary_motion_device_id="x")


def test_rejects_empty_primary_motion_device_id() -> None:
    with pytest.raises(ValueError):
        SynchronizationGroupConfig(group_id="left_lower_limb", primary_motion_device_id="")
