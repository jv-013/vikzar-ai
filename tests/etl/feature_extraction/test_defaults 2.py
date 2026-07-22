"""Unit tests for default_feature_modules()."""

from __future__ import annotations

from app.etl.feature_extraction import MotionFeatures, MuscleFeatures, PressureFeatures
from app.etl.feature_extraction.defaults import default_feature_modules


def test_covers_the_three_v1_domains() -> None:
    modules = default_feature_modules()

    assert set(modules.keys()) == {"motion", "pressure", "muscle"}
    assert isinstance(modules["motion"], MotionFeatures)
    assert isinstance(modules["pressure"], PressureFeatures)
    assert isinstance(modules["muscle"], MuscleFeatures)


def test_returns_a_fresh_dict_on_each_call() -> None:
    first = default_feature_modules()
    second = default_feature_modules()

    assert first is not second
