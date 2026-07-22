"""Unit tests for Publisher."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from app.etl.feature_validation import BiomarkerQuality, QualityFlag, QualityStatus, SetQualityObservation
from app.etl.publisher import Publisher
from app.schemas.quality_info import QualityStatusInfo
from app.schemas.raw_feature_vector import RawFeatureVector

from .helpers import make_aggregated_feature_cycle, make_player_session_context, make_validated_feature_set


def _publisher(on_published, context=None, id_factory=None, clock=None) -> Publisher:
    kwargs = dict(context=context or make_player_session_context(), on_published=on_published)
    if id_factory is not None:
        kwargs["id_factory"] = id_factory
    if clock is not None:
        kwargs["clock"] = clock
    return Publisher(**kwargs)


def test_lossless_mapping_of_a_valid_biomarker() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    validated = make_validated_feature_set(
        group_id="left_lower_limb", domains={"motion": {"peak_resultant_acceleration": 12.5}}
    )
    cycle = make_aggregated_feature_cycle(groups={"left_lower_limb": validated})

    publisher.handle(cycle)

    group = published[0].groups["left_lower_limb"]
    assert group.motion.biomarkers["peak_resultant_acceleration"] == 12.5
    assert group.motion.quality["peak_resultant_acceleration"].status == QualityStatusInfo.VALID


def test_rejected_biomarker_value_still_published_not_deleted() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    rejected = BiomarkerQuality(status=QualityStatus.REJECTED, flags=(QualityFlag.NON_FINITE_VALUE,), rationale="bad")
    validated = make_validated_feature_set(
        group_id="left_lower_limb",
        domains={"motion": {"peak_resultant_acceleration": float("nan")}},
        biomarker_quality={"motion": {"peak_resultant_acceleration": rejected}},
    )
    cycle = make_aggregated_feature_cycle(groups={"left_lower_limb": validated})

    publisher.handle(cycle)

    biomarker = published[0].groups["left_lower_limb"].motion.biomarkers["peak_resultant_acceleration"]
    quality = published[0].groups["left_lower_limb"].motion.quality["peak_resultant_acceleration"]
    assert biomarker != biomarker  # NaN, but present -- confidence, not deletion
    assert quality.status == QualityStatusInfo.REJECTED


def test_bilateral_preservation_two_groups_independent() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    left = make_validated_feature_set(group_id="left_lower_limb", domains={"motion": {"peak_resultant_acceleration": 1.0}})
    right = make_validated_feature_set(group_id="right_lower_limb", domains={"motion": {"peak_resultant_acceleration": 2.0}})
    cycle = make_aggregated_feature_cycle(groups={"left_lower_limb": left, "right_lower_limb": right})

    publisher.handle(cycle)

    groups = published[0].groups
    assert groups["left_lower_limb"].motion.biomarkers["peak_resultant_acceleration"] == 1.0
    assert groups["right_lower_limb"].motion.biomarkers["peak_resultant_acceleration"] == 2.0


def test_window_start_and_end_preserved_per_group() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    validated = make_validated_feature_set(group_id="left_lower_limb", window_start=500.0, window_end=1500.0)
    cycle = make_aggregated_feature_cycle(groups={"left_lower_limb": validated})

    publisher.handle(cycle)

    group = published[0].groups["left_lower_limb"]
    assert group.window_start == 500.0
    assert group.window_end == 1500.0


def test_set_observations_translated() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    observation = SetQualityObservation(
        flag=QualityFlag.EXPECTED_DOMAIN_ABSENT, domain="muscle", rationale="EMG configured but absent"
    )
    validated = make_validated_feature_set(group_id="left_lower_limb", set_observations=(observation,))
    cycle = make_aggregated_feature_cycle(groups={"left_lower_limb": validated})

    publisher.handle(cycle)

    published_observations = published[0].groups["left_lower_limb"].set_observations
    assert len(published_observations) == 1
    assert published_observations[0].domain == "muscle"
    assert published_observations[0].rationale == "EMG configured but absent"


def test_domain_absent_when_not_in_raw() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    validated = make_validated_feature_set(domains={"motion": {"peak_resultant_acceleration": 1.0}})
    cycle = make_aggregated_feature_cycle(groups={"left_lower_limb": validated})

    publisher.handle(cycle)

    group = published[0].groups["left_lower_limb"]
    assert group.motion is not None
    assert group.pressure is None
    assert group.muscle is None


def test_hardware_provenance_present() -> None:
    published: List[RawFeatureVector] = []
    context = make_player_session_context(firmware_revision="fw-2", hardware_revision="hw-2", protocol_version="2")
    publisher = _publisher(published.append, context=context)

    publisher.handle(make_aggregated_feature_cycle())

    hardware = published[0].hardware
    assert hardware.firmware_revision == "fw-2"
    assert hardware.hardware_revision == "hw-2"
    assert hardware.protocol_version == "2"


def test_player_session_and_schema_version_from_context() -> None:
    published: List[RawFeatureVector] = []
    context = make_player_session_context(schema_version="9.9.9", source="custom_source")
    publisher = _publisher(published.append, context=context)

    publisher.handle(make_aggregated_feature_cycle())

    assert published[0].schema_version == "9.9.9"
    assert published[0].source == "custom_source"
    assert published[0].player.player_id == context.player.player_id
    assert published[0].session.session_id == context.session.session_id


def test_id_factory_and_clock_are_used() -> None:
    published: List[RawFeatureVector] = []
    fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    publisher = _publisher(published.append, id_factory=lambda: "fixed-id", clock=lambda: fixed_time)

    publisher.handle(make_aggregated_feature_cycle())

    assert published[0].feature_vector_id == "fixed-id"
    assert published[0].timestamp == fixed_time


def test_unrecognized_domain_raises_and_drops_this_cycle_only() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    validated = make_validated_feature_set(domains={"locomotion": {"stride_length": 1.5}})
    cycle = make_aggregated_feature_cycle(groups={"left_lower_limb": validated})

    publisher.handle(cycle)  # must not raise -- caught internally, cycle dropped

    assert published == []


def test_handle_raises_type_error_for_non_aggregated_feature_cycle_input() -> None:
    publisher = _publisher(lambda rfv: None)

    with pytest.raises(TypeError):
        publisher.handle("not a cycle")  # type: ignore[arg-type]


def test_handle_raises_type_error_for_a_raw_feature_vector_fed_back_in() -> None:
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append)
    publisher.handle(make_aggregated_feature_cycle())
    assert published

    with pytest.raises(TypeError):
        publisher.handle(published[0])  # type: ignore[arg-type]


def test_handle_never_raises_when_on_published_callback_raises() -> None:
    def exploding_callback(rfv: RawFeatureVector) -> None:
        raise RuntimeError("simulated consumer failure")

    publisher = _publisher(exploding_callback)

    publisher.handle(make_aggregated_feature_cycle())  # must not raise


def test_deterministic_given_fixed_id_and_clock() -> None:
    fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    published: List[RawFeatureVector] = []
    publisher = _publisher(published.append, id_factory=lambda: "fixed-id", clock=lambda: fixed_time)
    cycle = make_aggregated_feature_cycle()

    publisher.handle(cycle)
    publisher.handle(cycle)

    first, second = published
    assert first.model_dump() == second.model_dump()
