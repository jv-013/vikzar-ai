"""Unit tests for default_window_specifications()."""

from __future__ import annotations

from app.etl.windowing.defaults import default_window_specifications
from app.config import etl_config


def test_returns_one_specification_matching_config() -> None:
    specs = default_window_specifications()

    assert len(specs) == 1
    assert specs[0].name == "primary"
    assert specs[0].duration_ms == etl_config.WINDOW_DURATION_MS
    assert specs[0].stride_ms == etl_config.WINDOW_STRIDE_MS


def test_stride_is_smaller_than_duration_overlap_enabled_by_default() -> None:
    specs = default_window_specifications()

    assert specs[0].stride_ms < specs[0].duration_ms
