"""Integration test: Synchronization -> Calibration.

Uses the real, frozen Synchronizer/GroupSynchronizer exactly as shipped —
this module requires no change to Synchronization to compose correctly.
"""

from __future__ import annotations

from typing import List

from app.etl.calibration import Calibrator, CalibratedFrame, default_calibration_functions
from app.etl.synchronization import SynchronizationGroupConfig, SyncStatus, Synchronizer

from .helpers import make_validated_packet

GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb",
    primary_motion_device_id="left_smart_pod",
    emg_device_id="left_emg_band",
)


def _build_pipeline(on_calibrated):
    calibrator = Calibrator(
        calibration_functions=default_calibration_functions(), on_calibrated=on_calibrated
    )
    synchronizer = Synchronizer(groups=[GROUP], on_synchronized=calibrator.handle)
    return synchronizer


def test_matched_frame_flows_through_synchronization_into_calibration() -> None:
    frames: List[CalibratedFrame] = []
    synchronizer = _build_pipeline(frames.append)

    synchronizer.handle(
        make_validated_packet(
            device_id="left_smart_pod",
            raw_channels={"accel_x": 100, "accel_y": -50, "accel_z": 300, "fsr_1": 500},
        )
    )
    synchronizer.handle(
        make_validated_packet(device_id="left_emg_band", raw_channels={"quadriceps": 11, "hamstring": 22})
    )

    assert len(frames) == 1
    frame = frames[0]
    assert frame.group_id == "left_lower_limb"
    assert frame.sync_status == SyncStatus.MATCHED
    assert "primary_motion" in frame.readings
    assert "emg" in frame.readings
    assert "accel_x" in frame.readings["primary_motion"].calibrated_channels
    assert "quadriceps" in frame.readings["emg"].calibrated_channels


def test_not_required_group_flows_through_with_no_emg_reading() -> None:
    frames: List[CalibratedFrame] = []
    match_mode_group = SynchronizationGroupConfig(
        group_id="right_lower_limb",
        primary_motion_device_id="right_smart_pod",
        emg_device_id=None,
    )
    calibrator = Calibrator(calibration_functions=default_calibration_functions(), on_calibrated=frames.append)
    synchronizer = Synchronizer(groups=[match_mode_group], on_synchronized=calibrator.handle)

    synchronizer.handle(make_validated_packet(device_id="right_smart_pod", raw_channels={"accel_x": 1}))

    assert len(frames) == 1
    assert frames[0].sync_status == SyncStatus.NOT_REQUIRED
    assert "emg" not in frames[0].readings
