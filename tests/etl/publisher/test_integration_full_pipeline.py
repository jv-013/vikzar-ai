"""Integration test: the complete bilateral ETL pipeline.

Synchronizer -> Calibrator -> Filterer -> Windower -> Extractor ->
FeatureValidator -> FeatureSetAggregator -> Publisher, using every
real, frozen upstream module, for two synchronization groups
(bilateral). Publisher requires no change to any of them to compose
correctly.
"""

from __future__ import annotations

from typing import List

from app.etl.aggregation import FeatureSetAggregator
from app.etl.calibration import Calibrator, default_calibration_functions
from app.etl.feature_extraction import Extractor
from app.etl.feature_extraction.defaults import default_feature_modules
from app.etl.feature_validation import FeatureValidator
from app.etl.feature_validation.defaults import default_validation_rules
from app.etl.filtering import Filterer, default_signal_filter_factories
from app.etl.publisher import Publisher
from app.etl.synchronization import SynchronizationGroupConfig, Synchronizer
from app.etl.windowing import WindowSpecification, Windower
from app.schemas.raw_feature_vector import RawFeatureVector

from ..calibration.helpers import make_validated_packet
from .helpers import make_player_session_context

LEFT_GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb", primary_motion_device_id="left_smart_pod", emg_device_id=None
)
RIGHT_GROUP = SynchronizationGroupConfig(
    group_id="right_lower_limb", primary_motion_device_id="right_smart_pod", emg_device_id=None
)
GROUPS = [LEFT_GROUP, RIGHT_GROUP]


def _build_pipeline(on_published):
    publisher = Publisher(context=make_player_session_context(), on_published=on_published)
    aggregator = FeatureSetAggregator(
        group_ids=[g.group_id for g in GROUPS], on_aggregated=publisher.handle
    )
    validator = FeatureValidator(
        rules=default_validation_rules(group_configs=GROUPS), on_validated=aggregator.handle
    )
    extractor = Extractor(feature_modules=default_feature_modules(), on_extracted=validator.handle)
    spec = WindowSpecification(name="primary", duration_ms=100.0, stride_ms=100.0)
    windower = Windower(window_specifications=[spec], on_window=extractor.handle)
    filterer = Filterer(filter_factory=default_signal_filter_factories(), on_filtered=windower.handle)
    calibrator = Calibrator(calibration_functions=default_calibration_functions(), on_calibrated=filterer.handle)
    synchronizer = Synchronizer(groups=GROUPS, on_synchronized=calibrator.handle)
    return synchronizer


def _emit_group(synchronizer: Synchronizer, device_id: str) -> None:
    for sequence_number, device_timestamp_ms in enumerate(range(0, 101, 10), start=1):
        synchronizer.handle(
            make_validated_packet(
                device_id=device_id,
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


def test_full_pipeline_publishes_a_bilateral_raw_feature_vector() -> None:
    published: List[RawFeatureVector] = []
    synchronizer = _build_pipeline(published.append)

    _emit_group(synchronizer, "left_smart_pod")
    assert published == []  # aggregator still waiting on the right group

    _emit_group(synchronizer, "right_smart_pod")

    assert len(published) == 1
    rfv = published[0]
    assert set(rfv.groups.keys()) == {"left_lower_limb", "right_lower_limb"}
    for group in rfv.groups.values():
        assert group.motion is not None
        assert group.motion.biomarkers["peak_resultant_acceleration"] == 100.0
        assert group.pressure is not None
        assert group.muscle is None  # Match Mode: no EMG configured

    # Full provenance chain intact end to end.
    assert rfv.player.player_id == "p1"
    assert rfv.hardware.firmware_revision == "fw-1.0.0"
    assert rfv.schema_version == "1.0.0"


def test_full_pipeline_is_deterministic_across_independent_runs() -> None:
    def run():
        published: List[RawFeatureVector] = []
        synchronizer = _build_pipeline(published.append)
        _emit_group(synchronizer, "left_smart_pod")
        _emit_group(synchronizer, "right_smart_pod")
        return published[0].groups["left_lower_limb"].motion.biomarkers

    assert run() == run()
