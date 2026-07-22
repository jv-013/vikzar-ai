"""Unit tests for AggregatedFeatureCycle."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.etl.aggregation import AggregatedFeatureCycle

from .helpers import make_validated_feature_set


def test_rejects_empty_groups() -> None:
    with pytest.raises(ValueError):
        AggregatedFeatureCycle(groups={})


def test_groups_is_immutable() -> None:
    cycle = AggregatedFeatureCycle(groups={"left_lower_limb": make_validated_feature_set()})

    assert isinstance(cycle.groups, MappingProxyType)
    with pytest.raises(TypeError):
        cycle.groups["right_lower_limb"] = make_validated_feature_set(group_id="right_lower_limb")
