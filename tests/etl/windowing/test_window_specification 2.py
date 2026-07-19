"""Unit tests for WindowSpecification."""

from __future__ import annotations

import pytest

from app.etl.windowing.window_specification import WindowSpecification


def test_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        WindowSpecification(name="", duration_ms=1000.0, stride_ms=100.0)


@pytest.mark.parametrize("duration_ms", [0.0, -1.0])
def test_rejects_non_positive_duration(duration_ms: float) -> None:
    with pytest.raises(ValueError):
        WindowSpecification(name="primary", duration_ms=duration_ms, stride_ms=100.0)


@pytest.mark.parametrize("stride_ms", [0.0, -1.0])
def test_rejects_non_positive_stride(stride_ms: float) -> None:
    with pytest.raises(ValueError):
        WindowSpecification(name="primary", duration_ms=1000.0, stride_ms=stride_ms)


def test_permits_stride_greater_than_duration() -> None:
    # Sparse windowing with gaps is a legitimate configuration.
    spec = WindowSpecification(name="sparse", duration_ms=100.0, stride_ms=2000.0)
    assert spec.stride_ms > spec.duration_ms
