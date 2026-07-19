"""
WindowSpecification: parameters describing one time-based window
configuration.

See docs/development/WINDOWING_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowSpecification:
    """
    Parameters describing one time-based window configuration.

    Purpose
        Decouple "how windows are shaped" (duration, stride) from
        Windower's own emission logic, so multiple window sizes can run
        concurrently over the same per-group frame history in a future
        version (e.g. 100ms, 250ms, 500ms, 1000ms simultaneously)
        without any change to Windower itself — only to how many
        WindowSpecification instances are configured.

    Attributes
        name: Identifies this specification (e.g. "primary"). Carried
            onto every Window this spec produces, so a downstream
            consumer running multiple concurrent specifications can
            tell which one produced a given Window.
        duration_ms: The window's span, in milliseconds, measured on
            frames' own reference_timestamp — never packet count and
            never wall-clock/monotonic processing time. BLE timing
            jitter changes how many packets land in a window; it never
            changes the window's intended temporal duration.
        stride_ms: How far, in milliseconds, the window's start
            advances between consecutive emissions. stride_ms <
            duration_ms yields overlapping windows; stride_ms ==
            duration_ms yields non-overlapping (back-to-back) windows;
            stride_ms > duration_ms yields sparse windows with gaps.
            Independent of duration_ms by design.

    Raises
        ValueError: If name is empty, or duration_ms/stride_ms is not
            strictly positive.
    """

    name: str
    duration_ms: float
    stride_ms: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("WindowSpecification.name must not be empty.")
        if self.duration_ms <= 0:
            raise ValueError("WindowSpecification.duration_ms must be positive.")
        if self.stride_ms <= 0:
            raise ValueError("WindowSpecification.stride_ms must be positive.")
