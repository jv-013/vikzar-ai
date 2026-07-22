"""Unit tests for FilteredFrame."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.etl.filtering.frame import FilteredFrame
from app.etl.synchronization import SyncStatus

from .helpers import make_filtered_reading


def test_rejects_empty_group_id() -> None:
    with pytest.raises(ValueError):
        FilteredFrame(
            group_id="",
            reference_timestamp=1000.0,
            sync_status=SyncStatus.MATCHED,
            readings={"primary_motion": make_filtered_reading()},
        )


def test_rejects_missing_primary_motion() -> None:
    with pytest.raises(ValueError):
        FilteredFrame(
            group_id="left_lower_limb",
            reference_timestamp=1000.0,
            sync_status=SyncStatus.MATCHED,
            readings={},
        )


def test_readings_is_immutable() -> None:
    frame = FilteredFrame(
        group_id="left_lower_limb",
        reference_timestamp=1000.0,
        sync_status=SyncStatus.MATCHED,
        readings={"primary_motion": make_filtered_reading()},
    )

    assert isinstance(frame.readings, MappingProxyType)
    with pytest.raises(TypeError):
        frame.readings["emg"] = make_filtered_reading()


def test_permits_emg_absent() -> None:
    frame = FilteredFrame(
        group_id="left_lower_limb",
        reference_timestamp=1000.0,
        sync_status=SyncStatus.NOT_REQUIRED,
        readings={"primary_motion": make_filtered_reading()},
    )

    assert "emg" not in frame.readings
