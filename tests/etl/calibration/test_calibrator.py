"""Unit tests for Calibrator."""

from __future__ import annotations

from typing import List

import pytest

from app.etl.calibration.calibrator import Calibrator
from app.etl.calibration.channel import CalibratedChannel
from app.etl.calibration.frame import CalibratedFrame
from app.etl.calibration.function import IMUCalibration
from app.etl.calibration.unit import PhysicalUnit
from app.etl.synchronization import SyncStatus

from .helpers import make_synchronized_frame, make_validated_packet

ACCEL = IMUCalibration(scale=0.5, offset=10.0, unit=PhysicalUnit.METERS_PER_SECOND_SQUARED)


def _calibrator(on_calibrated, calibration_functions=None) -> Calibrator:
    functions = calibration_functions if calibration_functions is not None else {"accel_x": ACCEL}
    return Calibrator(calibration_functions=functions, on_calibrated=on_calibrated)


def test_calibrates_a_matched_frame() -> None:
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    primary = make_validated_packet(device_id="smart_pod", raw_channels={"accel_x": 100})
    emg = make_validated_packet(device_id="emg_band", raw_channels={"quadriceps": 50})
    frame = make_synchronized_frame(
        group_id="left_lower_limb",
        sync_status=SyncStatus.MATCHED,
        packets={"primary_motion": primary, "emg": emg},
    )

    calibrator.handle(frame)

    assert len(frames) == 1
    calibrated = frames[0]
    assert calibrated.group_id == "left_lower_limb"
    assert calibrated.sync_status == SyncStatus.MATCHED
    assert calibrated.readings["primary_motion"].calibrated_channels["accel_x"] == CalibratedChannel(
        value=100 * 0.5 - 10.0, unit=PhysicalUnit.METERS_PER_SECOND_SQUARED
    )


def test_preserves_group_id_reference_timestamp_and_sync_status_unchanged() -> None:
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    frame = make_synchronized_frame(group_id="right_lower_limb", reference_timestamp=12345.5, sync_status=SyncStatus.NOT_REQUIRED)

    calibrator.handle(frame)

    assert frames[0].group_id == "right_lower_limb"
    assert frames[0].reference_timestamp == 12345.5
    assert frames[0].sync_status == SyncStatus.NOT_REQUIRED


def test_not_required_group_has_no_emg_reading() -> None:
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    frame = make_synchronized_frame(sync_status=SyncStatus.NOT_REQUIRED)

    calibrator.handle(frame)

    assert "emg" not in frames[0].readings


def test_timed_out_group_has_no_emg_reading_never_fabricated() -> None:
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    frame = make_synchronized_frame(
        sync_status=SyncStatus.TIMED_OUT,
        packets={"primary_motion": make_validated_packet(device_id="smart_pod"), "emg": None},
    )

    calibrator.handle(frame)

    assert "emg" not in frames[0].readings


def test_preserves_reading_provenance() -> None:
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    packet = make_validated_packet(
        device_id="smart_pod", sequence_number=7, device_timestamp_ms=2000, raw_channels={"accel_x": 1}
    )
    frame = make_synchronized_frame(packets={"primary_motion": packet})

    calibrator.handle(frame)

    reading = frames[0].readings["primary_motion"]
    assert reading.device_id == "smart_pod"
    assert reading.sequence_number == 7
    assert reading.device_timestamp_ms == 2000
    assert reading.received_at == packet.received_at
    assert reading.protocol_version == packet.protocol_version


def test_unconfigured_channel_is_skipped_not_guessed() -> None:
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append, calibration_functions={"accel_x": ACCEL})
    packet = make_validated_packet(raw_channels={"accel_x": 100, "totally_unknown_channel": 999})
    frame = make_synchronized_frame(packets={"primary_motion": packet})

    calibrator.handle(frame)

    channels = frames[0].readings["primary_motion"].calibrated_channels
    assert "accel_x" in channels
    assert "totally_unknown_channel" not in channels


def test_other_channels_still_calibrated_when_one_is_unconfigured() -> None:
    frames: List[CalibratedFrame] = []
    other = IMUCalibration(scale=1.0, offset=0.0, unit=PhysicalUnit.DEGREES_PER_SECOND)
    calibrator = _calibrator(frames.append, calibration_functions={"accel_x": ACCEL, "gyro_x": other})
    packet = make_validated_packet(raw_channels={"accel_x": 100, "gyro_x": 20, "unknown": 1})
    frame = make_synchronized_frame(packets={"primary_motion": packet})

    calibrator.handle(frame)

    channels = frames[0].readings["primary_motion"].calibrated_channels
    assert set(channels.keys()) == {"accel_x", "gyro_x"}


def test_per_channel_calibration_is_deterministic() -> None:
    outputs: List[CalibratedFrame] = []
    calibrator = _calibrator(outputs.append)
    packet = make_validated_packet(raw_channels={"accel_x": 100})
    frame = make_synchronized_frame(packets={"primary_motion": packet})

    calibrator.handle(frame)
    calibrator.handle(frame)

    first, second = outputs
    assert (
        first.readings["primary_motion"].calibrated_channels["accel_x"]
        == second.readings["primary_motion"].calibrated_channels["accel_x"]
    )


def test_two_groups_are_calibrated_independently_no_cross_group_leakage() -> None:
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    left = make_synchronized_frame(
        group_id="left_lower_limb",
        packets={"primary_motion": make_validated_packet(device_id="left_smart_pod", raw_channels={"accel_x": 10})},
    )
    right = make_synchronized_frame(
        group_id="right_lower_limb",
        packets={"primary_motion": make_validated_packet(device_id="right_smart_pod", raw_channels={"accel_x": 20})},
    )

    calibrator.handle(left)
    calibrator.handle(right)

    assert frames[0].group_id == "left_lower_limb"
    assert frames[1].group_id == "right_lower_limb"
    assert (
        frames[0].readings["primary_motion"].calibrated_channels["accel_x"]
        != frames[1].readings["primary_motion"].calibrated_channels["accel_x"]
    )


def test_handle_raises_type_error_for_non_synchronized_frame_input() -> None:
    calibrator = _calibrator(lambda frame: None)

    with pytest.raises(TypeError):
        calibrator.handle("not a frame")  # type: ignore[arg-type]


def test_handle_raises_type_error_for_a_calibrated_frame_fed_back_in() -> None:
    """The idempotency guarantee: a CalibratedFrame must never be
    recalibrated, and this is a hard, propagating failure, not a
    logged-and-swallowed one."""
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    frame = make_synchronized_frame()
    calibrator.handle(frame)
    already_calibrated = frames[0]

    with pytest.raises(TypeError):
        calibrator.handle(already_calibrated)  # type: ignore[arg-type]


def test_handle_never_raises_for_internal_errors() -> None:
    class ExplodingCalibration:
        def calibrate(self, raw_value: int) -> CalibratedChannel:
            raise RuntimeError("simulated calibration failure")

    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append, calibration_functions={"accel_x": ExplodingCalibration()})
    packet = make_validated_packet(raw_channels={"accel_x": 100})
    frame = make_synchronized_frame(packets={"primary_motion": packet})

    calibrator.handle(frame)  # must not raise

    assert frames == []


def test_never_calibrates_across_synchronization_group_configured_channels() -> None:
    """Sanity check that the calibration_functions registry is applied
    purely per-channel-name and never keyed by group in a way that could
    silently swap coefficients between groups."""
    frames: List[CalibratedFrame] = []
    calibrator = _calibrator(frames.append)
    packet_a = make_validated_packet(device_id="a", raw_channels={"accel_x": 1})
    packet_b = make_validated_packet(device_id="b", raw_channels={"accel_x": 1})

    calibrator.handle(make_synchronized_frame(group_id="group_a", packets={"primary_motion": packet_a}))
    calibrator.handle(make_synchronized_frame(group_id="group_b", packets={"primary_motion": packet_b}))

    assert (
        frames[0].readings["primary_motion"].calibrated_channels["accel_x"]
        == frames[1].readings["primary_motion"].calibrated_channels["accel_x"]
    )
