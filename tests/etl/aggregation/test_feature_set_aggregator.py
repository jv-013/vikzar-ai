"""Unit tests for FeatureSetAggregator."""

from __future__ import annotations

from typing import List

import pytest

from app.etl.aggregation import AggregatedFeatureCycle, FeatureSetAggregator

from .helpers import make_validated_feature_set


def test_constructor_rejects_empty_group_ids() -> None:
    with pytest.raises(ValueError):
        FeatureSetAggregator(group_ids=[], on_aggregated=lambda cycle: None)


def test_waits_until_every_configured_group_has_data() -> None:
    cycles: List[AggregatedFeatureCycle] = []
    aggregator = FeatureSetAggregator(
        group_ids=["left_lower_limb", "right_lower_limb"], on_aggregated=cycles.append
    )

    aggregator.handle(make_validated_feature_set(group_id="left_lower_limb"))
    assert cycles == []

    aggregator.handle(make_validated_feature_set(group_id="right_lower_limb"))
    assert len(cycles) == 1
    assert set(cycles[0].groups.keys()) == {"left_lower_limb", "right_lower_limb"}


def test_fifo_pairing_across_successive_cycles() -> None:
    cycles: List[AggregatedFeatureCycle] = []
    aggregator = FeatureSetAggregator(
        group_ids=["left_lower_limb", "right_lower_limb"], on_aggregated=cycles.append
    )

    left_1 = make_validated_feature_set(group_id="left_lower_limb", window_start=0.0, window_end=1000.0)
    left_2 = make_validated_feature_set(group_id="left_lower_limb", window_start=100.0, window_end=1100.0)
    right_1 = make_validated_feature_set(group_id="right_lower_limb", window_start=0.0, window_end=1000.0)
    right_2 = make_validated_feature_set(group_id="right_lower_limb", window_start=100.0, window_end=1100.0)

    aggregator.handle(left_1)
    aggregator.handle(left_2)
    aggregator.handle(right_1)
    aggregator.handle(right_2)

    assert len(cycles) == 2
    assert cycles[0].groups["left_lower_limb"] is left_1
    assert cycles[0].groups["right_lower_limb"] is right_1
    assert cycles[1].groups["left_lower_limb"] is left_2
    assert cycles[1].groups["right_lower_limb"] is right_2


def test_drains_multiple_complete_cycles_in_one_call() -> None:
    cycles: List[AggregatedFeatureCycle] = []
    aggregator = FeatureSetAggregator(
        group_ids=["left_lower_limb", "right_lower_limb"], on_aggregated=cycles.append
    )

    aggregator.handle(make_validated_feature_set(group_id="left_lower_limb", window_start=0.0, window_end=1000.0))
    aggregator.handle(make_validated_feature_set(group_id="left_lower_limb", window_start=100.0, window_end=1100.0))
    assert cycles == []

    # A single arrival for the lagging group should drain both queued cycles.
    aggregator.handle(make_validated_feature_set(group_id="right_lower_limb", window_start=0.0, window_end=1000.0))
    aggregator.handle(make_validated_feature_set(group_id="right_lower_limb", window_start=100.0, window_end=1100.0))

    assert len(cycles) == 2


def test_unconfigured_group_is_dropped_not_queued() -> None:
    cycles: List[AggregatedFeatureCycle] = []
    aggregator = FeatureSetAggregator(group_ids=["left_lower_limb"], on_aggregated=cycles.append)

    aggregator.handle(make_validated_feature_set(group_id="unconfigured_group"))

    assert cycles == []


def test_never_reads_across_groups() -> None:
    """A cycle's two entries are exactly the two independent objects
    given — the aggregator never inspects or alters either group's
    content while pairing them."""
    cycles: List[AggregatedFeatureCycle] = []
    aggregator = FeatureSetAggregator(
        group_ids=["left_lower_limb", "right_lower_limb"], on_aggregated=cycles.append
    )
    left = make_validated_feature_set(group_id="left_lower_limb", domains={"motion": {"peak_resultant_acceleration": 1.0}})
    right = make_validated_feature_set(group_id="right_lower_limb", domains={"motion": {"peak_resultant_acceleration": 99.0}})

    aggregator.handle(left)
    aggregator.handle(right)

    assert cycles[0].groups["left_lower_limb"].raw.domains["motion"]["peak_resultant_acceleration"] == 1.0
    assert cycles[0].groups["right_lower_limb"].raw.domains["motion"]["peak_resultant_acceleration"] == 99.0


def test_handle_raises_type_error_for_non_validated_feature_set_input() -> None:
    aggregator = FeatureSetAggregator(group_ids=["left_lower_limb"], on_aggregated=lambda cycle: None)

    with pytest.raises(TypeError):
        aggregator.handle("not a validated feature set")  # type: ignore[arg-type]


def test_handle_raises_type_error_for_an_aggregated_feature_cycle_fed_back_in() -> None:
    cycles: List[AggregatedFeatureCycle] = []
    aggregator = FeatureSetAggregator(group_ids=["left_lower_limb"], on_aggregated=cycles.append)
    aggregator.handle(make_validated_feature_set(group_id="left_lower_limb"))
    assert cycles

    with pytest.raises(TypeError):
        aggregator.handle(cycles[0])  # type: ignore[arg-type]


def test_handle_never_raises_when_on_aggregated_callback_raises() -> None:
    def exploding_callback(cycle: AggregatedFeatureCycle) -> None:
        raise RuntimeError("simulated consumer failure")

    aggregator = FeatureSetAggregator(group_ids=["left_lower_limb"], on_aggregated=exploding_callback)

    aggregator.handle(make_validated_feature_set(group_id="left_lower_limb"))  # must not raise


def test_deterministic_across_replays() -> None:
    def run():
        cycles: List[AggregatedFeatureCycle] = []
        aggregator = FeatureSetAggregator(
            group_ids=["left_lower_limb", "right_lower_limb"], on_aggregated=cycles.append
        )
        aggregator.handle(make_validated_feature_set(group_id="left_lower_limb"))
        aggregator.handle(make_validated_feature_set(group_id="right_lower_limb"))
        return len(cycles)

    assert run() == run() == 1
