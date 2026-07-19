"""
Window: the internal contract between Windowing and Feature Extraction.

Window is an ETL-internal type only, like RawPacket, ValidatedPacket,
SynchronizedFrame, CalibratedFrame, and FilteredFrame. It must never be
imported outside app/etl and has no relationship to RawFeatureVector or
EnhancedFeatureVector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.etl.filtering import FilteredFrame


@dataclass(frozen=True)
class Window:
    """
    One time-based window of FilteredFrames for a single synchronization
    group, from a single WindowSpecification.

    Purpose
        Carry a contiguous, time-bounded slice of a group's recent
        history to Feature Extraction. Contains zero computed values —
        only the raw sequence of FilteredFrames whose
        reference_timestamp falls within [window_start, window_end).
        Feature Extraction, not Windowing, is responsible for turning
        this into any biomechanical, statistical, or AI feature.

    Attributes
        group_id: Preserved unchanged from the source frames.
        window_specification_name: Which WindowSpecification produced
            this window (WindowSpecification.name) — lets a downstream
            consumer distinguish concurrently-running window sizes.
        window_start: Inclusive start of this window's time span, on
            the same reference_timestamp timeline as the source frames.
        window_end: Exclusive end of this window's time span
            (window_start + duration_ms, in the same units).
        frames: The FilteredFrames whose reference_timestamp falls
            within [window_start, window_end), in ascending timestamp
            order. May be empty — a group producing no data during
            this time span is a real fact, never fabricated or
            suppressed.

    Raises
        ValueError: If group_id or window_specification_name is empty,
            or window_end <= window_start.
    """

    group_id: str
    window_specification_name: str
    window_start: float
    window_end: float
    frames: Sequence[FilteredFrame]

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("Window.group_id must not be empty.")
        if not self.window_specification_name:
            raise ValueError("Window.window_specification_name must not be empty.")
        if self.window_end <= self.window_start:
            raise ValueError("Window.window_end must be greater than window_start.")
        object.__setattr__(self, "frames", tuple(self.frames))
