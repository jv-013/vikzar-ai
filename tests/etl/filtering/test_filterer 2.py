"""Unit tests for Filterer."""

from __future__ import annotations

from typing import List

import pytest

from app.etl.calibration import CalibratedChannel, PhysicalUnit
from app.etl.filtering.filterer import Filterer
from app.etl.filtering.frame import FilteredFrame
from app.etl.filtering.signal_filter import IMUFilter
from app.etl.synchronization import SyncStatus

from .helpers import make_calibrated_frame, make_calibrated_reading


def _filterer(on_filtered, filter_factory=None) -> Filterer:
    factory = filter_factory if filter_factory is not None else {"accel_x": lambda: IMUFilter(alpha=0.5)}
    return Filterer(filter_factory=factory, on_filtered=on_filtered)


def test_filters_a_matched_frame() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append)
    primary = make_calibrated_reading(device_id="smart_pod", calibrated_channels={"accel_x": CalibratedChannel(10.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)})
    frame = make_calibrated_frame(group_id="left_lower_limb", sync_status=SyncStatus.MATCHED, readings={"primary_motion": primary})

    filterer.handle(frame)

    assert len(frames) == 1
    filtered = frames[0]
    assert filtered.group_id == "left_lower_limb"
    assert filtered.sync_status == SyncStatus.MATCHED
    # first sample through a fresh filter is unchanged (bootstrap)
    assert filtered.readings["primary_motion"].filtered_channels["accel_x"].value == 10.0


def test_preserves_group_id_reference_timestamp_and_sync_status_unchanged() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append)
    frame = make_calibrated_frame(group_id="right_lower_limb", reference_timestamp=12345.5, sync_status=SyncStatus.NOT_REQUIRED)

    filterer.handle(frame)

    assert frames[0].group_id == "right_lower_limb"
    assert frames[0].reference_timestamp == 12345.5
    assert frames[0].sync_status == SyncStatus.NOT_REQUIRED


def test_not_required_group_has_no_emg_reading() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append)
    frame = make_calibrated_frame(sync_status=SyncStatus.NOT_REQUIRED)

    filterer.handle(frame)

    assert "emg" not in frames[0].readings


def test_preserves_reading_provenance() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append)
    reading = make_calibrated_reading(device_id="smart_pod", sequence_number=7, device_timestamp_ms=2000)
    frame = make_calibrated_frame(readings={"primary_motion": reading})

    filterer.handle(frame)

    filtered_reading = frames[0].readings["primary_motion"]
    assert filtered_reading.device_id == "smart_pod"
    assert filtered_reading.sequence_number == 7
    assert filtered_reading.device_timestamp_ms == 2000
    assert filtered_reading.protocol_version == reading.protocol_version


def test_preserves_the_unit_unchanged() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append)
    reading = make_calibrated_reading(
        calibrated_channels={"accel_x": CalibratedChannel(10.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)}
    )
    frame = make_calibrated_frame(readings={"primary_motion": reading})

    filterer.handle(frame)

    assert (
        frames[0].readings["primary_motion"].filtered_channels["accel_x"].unit
        == PhysicalUnit.METERS_PER_SECOND_SQUARED
    )


def test_unconfigured_channel_is_skipped_not_guessed() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append, filter_factory={"accel_x": lambda: IMUFilter(alpha=0.5)})
    reading = make_calibrated_reading(
        calibrated_channels={
            "accel_x": CalibratedChannel(1.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
            "totally_unknown_channel": CalibratedChannel(1.0, PhysicalUnit.VOLTS),
        }
    )
    frame = make_calibrated_frame(readings={"primary_motion": reading})

    filterer.handle(frame)

    channels = frames[0].readings["primary_motion"].filtered_channels
    assert "accel_x" in channels
    assert "totally_unknown_channel" not in channels


def test_state_persists_across_frames_for_the_same_group() -> None:
    """The core new behavior versus Calibration: a second frame from the
    same group must be smoothed against the first frame's output, not
    treated as an independent bootstrap."""
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append, filter_factory={"accel_x": lambda: IMUFilter(alpha=0.5)})
    reading_1 = make_calibrated_reading(calibrated_channels={"accel_x": CalibratedChannel(10.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)})
    reading_2 = make_calibrated_reading(calibrated_channels={"accel_x": CalibratedChannel(20.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)})

    filterer.handle(make_calibrated_frame(group_id="left_lower_limb", readings={"primary_motion": reading_1}))
    filterer.handle(make_calibrated_frame(group_id="left_lower_limb", readings={"primary_motion": reading_2}))

    first_value = frames[0].readings["primary_motion"].filtered_channels["accel_x"].value
    second_value = frames[1].readings["primary_motion"].filtered_channels["accel_x"].value
    assert first_value == 10.0
    assert second_value == 0.5 * 20.0 + 0.5 * 10.0


def test_two_groups_have_independent_filter_state_no_cross_group_state() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append, filter_factory={"accel_x": lambda: IMUFilter(alpha=0.5)})
    left_reading = make_calibrated_reading(calibrated_channels={"accel_x": CalibratedChannel(100.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)})
    right_reading = make_calibrated_reading(calibrated_channels={"accel_x": CalibratedChannel(0.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)})

    # Warm up left_lower_limb's state with two samples.
    filterer.handle(make_calibrated_frame(group_id="left_lower_limb", readings={"primary_motion": left_reading}))
    filterer.handle(make_calibrated_frame(group_id="left_lower_limb", readings={"primary_motion": left_reading}))
    # right_lower_limb's first-ever sample must bootstrap independently, unaffected by left's history.
    filterer.handle(make_calibrated_frame(group_id="right_lower_limb", readings={"primary_motion": right_reading}))

    right_value = frames[2].readings["primary_motion"].filtered_channels["accel_x"].value
    assert right_value == 0.0


def test_two_channels_within_one_group_have_independent_filter_state() -> None:
    """Preserves temporal relationships between channels: accel_x and
    accel_y must never share filter history."""
    frames: List[FilteredFrame] = []
    filterer = _filterer(
        frames.append,
        filter_factory={"accel_x": lambda: IMUFilter(alpha=0.5), "accel_y": lambda: IMUFilter(alpha=0.5)},
    )
    reading_1 = make_calibrated_reading(
        calibrated_channels={
            "accel_x": CalibratedChannel(100.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
            "accel_y": CalibratedChannel(0.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
        }
    )
    reading_2 = make_calibrated_reading(
        calibrated_channels={
            "accel_x": CalibratedChannel(100.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
            "accel_y": CalibratedChannel(0.0, PhysicalUnit.METERS_PER_SECOND_SQUARED),
        }
    )

    filterer.handle(make_calibrated_frame(readings={"primary_motion": reading_1}))
    filterer.handle(make_calibrated_frame(readings={"primary_motion": reading_2}))

    channels = frames[1].readings["primary_motion"].filtered_channels
    assert channels["accel_x"].value == 100.0
    assert channels["accel_y"].value == 0.0


def test_handle_raises_type_error_for_non_calibrated_frame_input() -> None:
    filterer = _filterer(lambda frame: None)

    with pytest.raises(TypeError):
        filterer.handle("not a frame")  # type: ignore[arg-type]


def test_handle_raises_type_error_for_a_filtered_frame_fed_back_in() -> None:
    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append)
    filterer.handle(make_calibrated_frame())
    already_filtered = frames[0]

    with pytest.raises(TypeError):
        filterer.handle(already_filtered)  # type: ignore[arg-type]


def test_handle_never_raises_for_internal_errors() -> None:
    class ExplodingFilter:
        def filter(self, value: float) -> float:
            raise RuntimeError("simulated filter failure")

    frames: List[FilteredFrame] = []
    filterer = _filterer(frames.append, filter_factory={"accel_x": lambda: ExplodingFilter()})
    frame = make_calibrated_frame(
        readings={"primary_motion": make_calibrated_reading(calibrated_channels={"accel_x": CalibratedChannel(1.0, PhysicalUnit.METERS_PER_SECOND_SQUARED)})}
    )

    filterer.handle(frame)  # must not raise

    assert frames == []
