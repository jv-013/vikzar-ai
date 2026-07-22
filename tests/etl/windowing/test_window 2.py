"""Unit tests for Window."""

from __future__ import annotations

import pytest

from app.etl.windowing.window import Window

from .helpers import make_filtered_frame


def test_rejects_empty_group_id() -> None:
    with pytest.raises(ValueError):
        Window(group_id="", window_specification_name="primary", window_start=0.0, window_end=1000.0, frames=())


def test_rejects_empty_window_specification_name() -> None:
    with pytest.raises(ValueError):
        Window(group_id="left_lower_limb", window_specification_name="", window_start=0.0, window_end=1000.0, frames=())


def test_rejects_window_end_not_after_window_start() -> None:
    with pytest.raises(ValueError):
        Window(group_id="left_lower_limb", window_specification_name="primary", window_start=1000.0, window_end=1000.0, frames=())


def test_permits_empty_frames() -> None:
    window = Window(group_id="left_lower_limb", window_specification_name="primary", window_start=0.0, window_end=1000.0, frames=())
    assert window.frames == ()


def test_frames_is_stored_as_an_immutable_tuple() -> None:
    frame = make_filtered_frame(reference_timestamp=10.0)
    window = Window(group_id="left_lower_limb", window_specification_name="primary", window_start=0.0, window_end=1000.0, frames=[frame])

    assert isinstance(window.frames, tuple)
    assert window.frames == (frame,)
