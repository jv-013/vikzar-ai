"""Integration test: Filtering -> Windowing.

Uses the real, frozen Filterer (with real Calibrator upstream) exactly
as shipped — this module requires no change to either to compose
correctly.
"""

from __future__ import annotations

from typing import List

from app.etl.calibration import Calibrator, default_calibration_functions
from app.etl.filtering import Filterer, default_signal_filter_factories
from app.etl.synchronization import SynchronizationGroupConfig, Synchronizer
from app.etl.windowing import Window, WindowSpecification, Windower

from ..calibration.helpers import make_validated_packet

MATCH_MODE_GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb",
    primary_motion_device_id="left_smart_pod",
    emg_device_id=None,
)


def test_frames_flow_through_filtering_into_a_window() -> None:
    windows: List[Window] = []
    spec = WindowSpecification(name="primary", duration_ms=100.0, stride_ms=100.0)
    windower = Windower(window_specifications=[spec], on_window=windows.append)
    filterer = Filterer(filter_factory=default_signal_filter_factories(), on_filtered=windower.handle)
    calibrator = Calibrator(calibration_functions=default_calibration_functions(), on_calibrated=filterer.handle)
    synchronizer = Synchronizer(groups=[MATCH_MODE_GROUP], on_synchronized=calibrator.handle)

    # Ten packets 10ms apart (via device_timestamp_ms), followed by one
    # packet crossing the 100ms boundary to trigger emission.
    for sequence_number, device_timestamp_ms in enumerate(range(0, 101, 10), start=1):
        synchronizer.handle(
            make_validated_packet(
                device_id="left_smart_pod",
                sequence_number=sequence_number,
                device_timestamp_ms=device_timestamp_ms,
                raw_channels={"accel_x": 100},
            )
        )

    assert len(windows) == 1
    window = windows[0]
    assert window.group_id == "left_lower_limb"
    assert window.window_specification_name == "primary"
    assert len(window.frames) == 10
    assert all("accel_x" in f.readings["primary_motion"].filtered_channels for f in window.frames)
