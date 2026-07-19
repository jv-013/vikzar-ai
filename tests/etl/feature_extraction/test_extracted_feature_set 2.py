"""Unit tests for ExtractedFeatureSet."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from app.etl.feature_extraction import ExtractedFeatureSet


def _feature_set(**overrides) -> ExtractedFeatureSet:
    defaults = dict(
        group_id="left_lower_limb",
        window_specification_name="primary",
        window_start=0.0,
        window_end=1000.0,
        domains={"motion": {"peak_resultant_acceleration": 5.0}},
        sample_counts={"motion": 10},
    )
    defaults.update(overrides)
    return ExtractedFeatureSet(**defaults)


def test_rejects_empty_group_id() -> None:
    with pytest.raises(ValueError):
        _feature_set(group_id="")


def test_rejects_empty_window_specification_name() -> None:
    with pytest.raises(ValueError):
        _feature_set(window_specification_name="")


def test_rejects_window_end_not_after_window_start() -> None:
    with pytest.raises(ValueError):
        _feature_set(window_start=1000.0, window_end=1000.0)


def test_rejects_sample_counts_keys_not_matching_domains_keys() -> None:
    with pytest.raises(ValueError):
        _feature_set(
            domains={"motion": {"peak_resultant_acceleration": 5.0}},
            sample_counts={"pressure": 10},
        )


def test_permits_empty_domains_and_sample_counts() -> None:
    feature_set = _feature_set(domains={}, sample_counts={})
    assert feature_set.domains == {}
    assert feature_set.sample_counts == {}


def test_domains_and_nested_feature_maps_are_immutable() -> None:
    feature_set = _feature_set()

    assert isinstance(feature_set.domains, MappingProxyType)
    assert isinstance(feature_set.domains["motion"], MappingProxyType)
    with pytest.raises(TypeError):
        feature_set.domains["pressure"] = {}
    with pytest.raises(TypeError):
        feature_set.domains["motion"]["new_feature"] = 1.0


def test_sample_counts_is_immutable() -> None:
    feature_set = _feature_set()

    assert isinstance(feature_set.sample_counts, MappingProxyType)
    with pytest.raises(TypeError):
        feature_set.sample_counts["motion"] = 999
