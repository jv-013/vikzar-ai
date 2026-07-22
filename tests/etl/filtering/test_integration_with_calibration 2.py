"""Integration test: Calibration -> Filtering.

Uses the real, frozen Calibrator exactly as shipped — this module
requires no change to Calibration to compose correctly.
"""

from __future__ import annotations

from typing import List

from app.etl.calibration import Calibrator, default_calibration_functions
from app.etl.filtering import Filterer, FilteredFrame, default_signal_filter_factories
from app.etl.synchronization import SynchronizationGroupConfig, SyncStatus, Synchronizer

from ..calibration.helpers import make_validated_packet

GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb",
    primary_motion_device_id="left_smart_pod",
    emg_device_id="left_emg_band",
)


def _build_pipeline(on_filtered):
    filterer = Filterer(filter_factory=default_signal_filter_factories(), on_filtered=on_filtered)
    calibrator = Calibrator(calibration_functions=default_calibration_functions(), on_calibrated=filterer.handle)
    synchronizer = Synchronizer(groups=[GROUP], on_synchronized=calibrator.handle)
    return synchronizer


def test_matched_frame_flows_through_calibration_into_filtering() -> None:
    frames: List[FilteredFrame] = []
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
    assert "accel_x" in frame.readings["primary_motion"].filtered_channels
    assert "quadriceps" in frame.readings["emg"].filtered_channels


def test_state_persists_through_the_full_chain_across_two_frames() -> None:
    frames: List[FilteredFrame] = []
    match_mode_group = SynchronizationGroupConfig(
        group_id="left_lower_limb",
        primary_motion_device_id="left_smart_pod",
        emg_device_id=None,
    )
    filterer = Filterer(filter_factory=default_signal_filter_factories(), on_filtered=frames.append)
    calibrator = Calibrator(calibration_functions=default_calibration_functions(), on_calibrated=filterer.handle)
    synchronizer = Synchronizer(groups=[match_mode_group], on_synchronized=calibrator.handle)

    for sequence_number in (1, 2):
        synchronizer.handle(
            make_validated_packet(
                device_id="left_smart_pod",
                sequence_number=sequence_number,
                raw_channels={"accel_x": 100},
            )
        )

    assert len(frames) == 2
    # Default DEV_ACCEL_FILTER_ALPHA=1.0 is a passthrough, so both frames'
    # filtered value should simply equal the calibrated (identity) value —
    # this proves the whole chain composes end to end without erroring,
    # independent of whichever alpha etl_config happens to be set to.
    first = frames[0].readings["primary_motion"].filtered_channels["accel_x"].value
    second = frames[1].readings["primary_motion"].filtered_channels["accel_x"].value
    assert first == second == 100.0
