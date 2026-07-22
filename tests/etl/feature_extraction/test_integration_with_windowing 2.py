"""Integration test: Windowing -> Feature Extraction.

Uses the real, frozen Windower (with real Filterer/Calibrator/Synchronizer
upstream) exactly as shipped — this module requires no change to any of
them to compose correctly.
"""

from __future__ import annotations

from typing import List

from app.etl.calibration import Calibrator, default_calibration_functions
from app.etl.feature_extraction import ExtractedFeatureSet, Extractor
from app.etl.feature_extraction.defaults import default_feature_modules
from app.etl.filtering import Filterer, default_signal_filter_factories
from app.etl.synchronization import SynchronizationGroupConfig, Synchronizer
from app.etl.windowing import WindowSpecification, Windower

from ..calibration.helpers import make_validated_packet

MATCH_MODE_GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb",
    primary_motion_device_id="left_smart_pod",
    emg_device_id=None,
)


def test_full_pipeline_produces_extracted_features() -> None:
    feature_sets: List[ExtractedFeatureSet] = []
    extractor = Extractor(feature_modules=default_feature_modules(), on_extracted=feature_sets.append)
    spec = WindowSpecification(name="primary", duration_ms=100.0, stride_ms=100.0)
    windower = Windower(window_specifications=[spec], on_window=extractor.handle)
    filterer = Filterer(filter_factory=default_signal_filter_factories(), on_filtered=windower.handle)
    calibrator = Calibrator(calibration_functions=default_calibration_functions(), on_calibrated=filterer.handle)
    synchronizer = Synchronizer(groups=[MATCH_MODE_GROUP], on_synchronized=calibrator.handle)

    for sequence_number, device_timestamp_ms in enumerate(range(0, 101, 10), start=1):
        synchronizer.handle(
            make_validated_packet(
                device_id="left_smart_pod",
                sequence_number=sequence_number,
                device_timestamp_ms=device_timestamp_ms,
                raw_channels={"accel_x": 100, "accel_y": 0, "accel_z": 0, "fsr_1": 50, "fsr_2": 50, "fsr_3": 50},
            )
        )

    assert len(feature_sets) == 1
    result = feature_sets[0]
    assert result.group_id == "left_lower_limb"
    assert "motion" in result.domains
    assert "pressure" in result.domains
    assert "muscle" not in result.domains  # Match Mode: no EMG this session
    assert result.domains["motion"]["peak_resultant_acceleration"] == 100.0
