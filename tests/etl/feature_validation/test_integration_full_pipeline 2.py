"""Integration test: the complete 8-stage ETL pipeline.

Synchronizer -> Calibrator -> Filterer -> Windower -> Extractor ->
FeatureValidator, using every real, frozen upstream module. Feature
Validation requires no change to any of them to compose correctly.
"""

from __future__ import annotations

from typing import List

from app.etl.calibration import Calibrator, default_calibration_functions
from app.etl.feature_extraction import Extractor
from app.etl.feature_extraction.defaults import default_feature_modules
from app.etl.feature_validation import QualityStatus, ValidatedFeatureSet
from app.etl.feature_validation.defaults import default_validation_rules
from app.etl.feature_validation.feature_validator import FeatureValidator
from app.etl.filtering import Filterer, default_signal_filter_factories
from app.etl.synchronization import SynchronizationGroupConfig, Synchronizer
from app.etl.windowing import WindowSpecification, Windower

from ..calibration.helpers import make_validated_packet

MATCH_MODE_GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb",
    primary_motion_device_id="left_smart_pod",
    emg_device_id=None,
)


def test_full_pipeline_produces_validated_features() -> None:
    validated_sets: List[ValidatedFeatureSet] = []
    validator = FeatureValidator(
        rules=default_validation_rules(group_configs=[MATCH_MODE_GROUP]),
        on_validated=validated_sets.append,
    )
    extractor = Extractor(feature_modules=default_feature_modules(), on_extracted=validator.handle)
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
                raw_channels={
                    "accel_x": 100,
                    "accel_y": 0,
                    "accel_z": 0,
                    "fsr_1": 50,
                    "fsr_2": 50,
                    "fsr_3": 50,
                },
            )
        )

    assert len(validated_sets) == 1
    validated = validated_sets[0]
    assert validated.raw.group_id == "left_lower_limb"
    assert "motion" in validated.biomarker_quality
    assert "pressure" in validated.biomarker_quality
    assert "muscle" not in validated.biomarker_quality  # Match Mode: no EMG this session

    # No set-level observation should complain about muscle being
    # absent, since this group has no EMG configured.
    muscle_observations = [obs for obs in validated.set_observations if obs.domain == "muscle"]
    assert muscle_observations == []

    # peak_resultant_acceleration is well-formed and mathematically
    # consistent, so it should be VALID (not REJECTED) even though the
    # window only has 10 samples against a 100-sample nominal count for
    # a 1000ms window — because this window is only 100ms, so its own
    # nominal count is much lower.
    motion_quality = validated.biomarker_quality["motion"]["peak_resultant_acceleration"]
    assert motion_quality.status in (QualityStatus.VALID, QualityStatus.QUESTIONABLE)
