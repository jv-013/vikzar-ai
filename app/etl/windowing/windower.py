"""
Windowing.

Stage 6 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/WINDOWING_DESIGN.md).

Owns all temporal window management for ETL: maintains per-group frame
history, emits time-based windows per configured WindowSpecification,
and manages overlap/stride behavior. Computes nothing — never a
biomechanical, statistical, or AI feature. Feature Extraction (next
stage) owns all feature computation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence, Tuple

from app.etl.filtering import FilteredFrame

from .window import Window
from .window_specification import WindowSpecification

logger = logging.getLogger(__name__)

WindowConsumer = Callable[[Window], None]
"""Invoked with each Window as it is emitted."""


@dataclass
class _GroupState:
    """Per-group mutable state: buffered frame history, and, per
    WindowSpecification name, that specification's next window start."""

    frame_history: List[FilteredFrame] = field(default_factory=list)
    next_window_start: Dict[str, float] = field(default_factory=dict)


class Windower:
    """
    Converts a stream of FilteredFrames into time-based Windows.

    Purpose
        Maintain a per-group_id buffer of recent FilteredFrames and, for
        every configured WindowSpecification, emit a Window each time
        enough elapsed time (measured on frames' own
        reference_timestamp) has passed since that specification's last
        emission for that group. Never merges or compares groups; never
        computes a feature.

    State isolation
        Each group_id owns its own frame history and its own
        per-specification next-window-start tracking, entirely
        independent of every other group (no cross-group state, no
        cross-group windowing). All configured WindowSpecifications
        read from the same shared per-group history — adding a second
        concurrently-running specification does not duplicate storage.

    Idempotency
        handle() only ever accepts a FilteredFrame and raises
        TypeError immediately, outside the internal try/except, for
        anything else — the same fail-loud-on-wiring-bugs discipline
        as Calibration and Filtering. Windowing carries even more
        per-group state than Filtering (a full history buffer, plus
        per-specification progress), so reprocessing or misordering a
        frame would corrupt that state for every window emitted after
        it, exactly as with Filtering.
    """

    def __init__(
        self,
        window_specifications: Sequence[WindowSpecification],
        on_window: WindowConsumer,
    ) -> None:
        """
        Initialize the windower.

        Args:
            window_specifications: The window configurations to emit
                concurrently. Must be non-empty.
            on_window: Callback invoked with each emitted Window.

        Raises:
            ValueError: If window_specifications is empty.
        """
        if not window_specifications:
            raise ValueError("Windower requires at least one WindowSpecification.")
        self._window_specifications: Tuple[WindowSpecification, ...] = tuple(window_specifications)
        self._max_duration_ms: float = max(spec.duration_ms for spec in self._window_specifications)
        self._on_window = on_window
        self._group_state: Dict[str, _GroupState] = {}

    def handle(self, frame: FilteredFrame) -> None:
        """
        Process a single FilteredFrame, emitting zero or more Windows.

        This is the entry point wired as Filterer's on_filtered
        callback. Data-quality problems are logged and degraded
        gracefully; a wrong input type is a wiring bug and raises
        immediately. See the idempotency note above.

        Args:
            frame: The frame to buffer/window.

        Raises:
            TypeError: If frame is not a FilteredFrame.
        """
        if not isinstance(frame, FilteredFrame):
            raise TypeError(
                f"Windower.handle() only accepts FilteredFrame; received "
                f"{type(frame).__name__}."
            )
        try:
            self._handle(frame)
        except Exception:
            logger.exception(
                "windower.unexpected_error",
                extra={"group_id": frame.group_id},
            )

    def _handle(self, frame: FilteredFrame) -> None:
        state = self._group_state.setdefault(frame.group_id, _GroupState())
        state.frame_history.append(frame)

        for spec in self._window_specifications:
            self._emit_due_windows(frame.group_id, state, spec)

        self._trim_history(state, frame.reference_timestamp)

    def _emit_due_windows(self, group_id: str, state: _GroupState, spec: WindowSpecification) -> None:
        if spec.name not in state.next_window_start:
            state.next_window_start[spec.name] = state.frame_history[0].reference_timestamp

        latest_timestamp = state.frame_history[-1].reference_timestamp
        while latest_timestamp >= state.next_window_start[spec.name] + spec.duration_ms:
            window_start = state.next_window_start[spec.name]
            window_end = window_start + spec.duration_ms
            frames_in_window = tuple(
                sorted(
                    (f for f in state.frame_history if window_start <= f.reference_timestamp < window_end),
                    key=lambda f: f.reference_timestamp,
                )
            )
            window = Window(
                group_id=group_id,
                window_specification_name=spec.name,
                window_start=window_start,
                window_end=window_end,
                frames=frames_in_window,
            )
            self._on_window(window)
            state.next_window_start[spec.name] = window_start + spec.stride_ms

    def _trim_history(self, state: _GroupState, latest_timestamp: float) -> None:
        cutoff = latest_timestamp - self._max_duration_ms
        state.frame_history = [f for f in state.frame_history if f.reference_timestamp >= cutoff]
