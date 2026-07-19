"""Unit tests for Windower."""

from __future__ import annotations

from typing import List

import pytest

from app.etl.windowing import Window, WindowSpecification, Windower

from .helpers import make_filtered_frame


def test_constructor_rejects_empty_window_specifications() -> None:
    with pytest.raises(ValueError):
        Windower(window_specifications=[], on_window=lambda window: None)


def test_windows_are_emitted_at_correct_time_boundaries_with_overlap() -> None:
    windows: List[Window] = []
    spec = WindowSpecification(name="w", duration_ms=100.0, stride_ms=50.0)
    windower = Windower(window_specifications=[spec], on_window=windows.append)

    for t in range(0, 201, 10):
        windower.handle(make_filtered_frame(reference_timestamp=float(t)))

    assert [w.window_start for w in windows] == [0.0, 50.0, 100.0]
    assert [w.window_end for w in windows] == [100.0, 150.0, 200.0]
    assert [f.reference_timestamp for f in windows[0].frames] == [float(t) for t in range(0, 100, 10)]
    assert [f.reference_timestamp for f in windows[1].frames] == [float(t) for t in range(50, 150, 10)]

    overlap = {f.reference_timestamp for f in windows[0].frames} & {f.reference_timestamp for f in windows[1].frames}
    assert overlap == {50.0, 60.0, 70.0, 80.0, 90.0}


def test_window_boundaries_are_time_based_not_packet_count() -> None:
    windows: List[Window] = []
    spec = WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)
    windower = Windower(window_specifications=[spec], on_window=windows.append)

    jittery_timestamps = [0.0, 5.0, 30.0, 32.0, 90.0, 95.0, 100.0]
    for t in jittery_timestamps:
        windower.handle(make_filtered_frame(reference_timestamp=t))

    assert len(windows) == 1
    assert windows[0].window_start == 0.0
    assert windows[0].window_end == 100.0
    assert len(windows[0].frames) == 6


def test_window_closes_at_same_elapsed_time_regardless_of_packet_count_inside() -> None:
    spec = WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)

    sparse_windows: List[Window] = []
    sparse = Windower(window_specifications=[spec], on_window=sparse_windows.append)
    for t in [0.0, 100.0]:
        sparse.handle(make_filtered_frame(reference_timestamp=t))

    dense_windows: List[Window] = []
    dense = Windower(window_specifications=[spec], on_window=dense_windows.append)
    for t in range(0, 101, 10):
        dense.handle(make_filtered_frame(reference_timestamp=float(t)))

    assert len(sparse_windows) == len(dense_windows) == 1
    assert sparse_windows[0].window_start == dense_windows[0].window_start == 0.0
    assert sparse_windows[0].window_end == dense_windows[0].window_end == 100.0
    assert len(sparse_windows[0].frames) == 1
    assert len(dense_windows[0].frames) == 10


def test_gap_in_data_emits_multiple_windows_including_empty_ones() -> None:
    windows: List[Window] = []
    spec = WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)
    windower = Windower(window_specifications=[spec], on_window=windows.append)

    windower.handle(make_filtered_frame(reference_timestamp=0.0))
    assert windows == []

    windower.handle(make_filtered_frame(reference_timestamp=350.0))

    assert [w.window_start for w in windows] == [0.0, 100.0, 200.0]
    assert len(windows[0].frames) == 1
    assert windows[1].frames == ()
    assert windows[2].frames == ()


def test_multiple_concurrent_specifications_emit_independently_from_shared_history() -> None:
    windows: List[Window] = []
    short_spec = WindowSpecification(name="short", duration_ms=100.0, stride_ms=100.0)
    long_spec = WindowSpecification(name="long", duration_ms=200.0, stride_ms=200.0)
    windower = Windower(window_specifications=[short_spec, long_spec], on_window=windows.append)

    for t in range(0, 201, 10):
        windower.handle(make_filtered_frame(reference_timestamp=float(t)))

    short_windows = [w for w in windows if w.window_specification_name == "short"]
    long_windows = [w for w in windows if w.window_specification_name == "long"]
    assert [w.window_start for w in short_windows] == [0.0, 100.0]
    assert [w.window_start for w in long_windows] == [0.0]
    assert len(long_windows[0].frames) == 20


def test_two_groups_have_independent_windowing_state_no_cross_group_windows() -> None:
    windows: List[Window] = []
    spec = WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)
    windower = Windower(window_specifications=[spec], on_window=windows.append)

    windower.handle(make_filtered_frame(group_id="left_lower_limb", reference_timestamp=0.0))
    windower.handle(make_filtered_frame(group_id="left_lower_limb", reference_timestamp=100.0))
    windower.handle(make_filtered_frame(group_id="right_lower_limb", reference_timestamp=500.0))
    windower.handle(make_filtered_frame(group_id="right_lower_limb", reference_timestamp=600.0))

    left_windows = [w for w in windows if w.group_id == "left_lower_limb"]
    right_windows = [w for w in windows if w.group_id == "right_lower_limb"]
    assert len(left_windows) == 1
    assert left_windows[0].window_start == 0.0
    assert len(right_windows) == 1
    assert right_windows[0].window_start == 500.0


def test_frame_history_is_trimmed_to_bound_memory() -> None:
    spec = WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)
    windower = Windower(window_specifications=[spec], on_window=lambda window: None)

    for t in range(0, 5001, 10):
        windower.handle(make_filtered_frame(reference_timestamp=float(t)))

    history_length = len(windower._group_state["left_lower_limb"].frame_history)
    assert history_length <= 11


def test_handle_raises_type_error_for_non_filtered_frame_input() -> None:
    windower = Windower(
        window_specifications=[WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)],
        on_window=lambda window: None,
    )

    with pytest.raises(TypeError):
        windower.handle("not a frame")  # type: ignore[arg-type]


def test_handle_raises_type_error_for_a_window_fed_back_in() -> None:
    windows: List[Window] = []
    windower = Windower(
        window_specifications=[WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)],
        on_window=windows.append,
    )
    windower.handle(make_filtered_frame(reference_timestamp=0.0))
    windower.handle(make_filtered_frame(reference_timestamp=100.0))
    assert windows

    with pytest.raises(TypeError):
        windower.handle(windows[0])  # type: ignore[arg-type]


def test_handle_never_raises_when_on_window_callback_raises() -> None:
    def exploding_callback(window: Window) -> None:
        raise RuntimeError("simulated consumer failure")

    windower = Windower(
        window_specifications=[WindowSpecification(name="w", duration_ms=100.0, stride_ms=100.0)],
        on_window=exploding_callback,
    )

    windower.handle(make_filtered_frame(reference_timestamp=0.0))
    windower.handle(make_filtered_frame(reference_timestamp=100.0))  # must not raise


def test_deterministic_across_replays() -> None:
    def run():
        windows: List[Window] = []
        windower = Windower(
            window_specifications=[WindowSpecification(name="w", duration_ms=100.0, stride_ms=50.0)],
            on_window=windows.append,
        )
        for t in range(0, 301, 10):
            windower.handle(make_filtered_frame(reference_timestamp=float(t)))
        return [(w.window_start, w.window_end, len(w.frames)) for w in windows]

    assert run() == run()
