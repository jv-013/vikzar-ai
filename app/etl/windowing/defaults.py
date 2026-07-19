"""
Default WindowSpecification registry, assembled from
app.config.etl_config.

See docs/development/WINDOWING_DESIGN.md.
"""

from __future__ import annotations

from typing import Sequence

from app.config import etl_config

from .window_specification import WindowSpecification


def default_window_specifications() -> Sequence[WindowSpecification]:
    """
    Build the default WindowSpecification sequence.

    V1 configures exactly one specification, but the return type is
    already a sequence — extending to concurrent multi-window support
    (e.g. adding 100ms/250ms/500ms specifications alongside this one)
    is a config-only change here, not a Windower redesign.
    """
    return (
        WindowSpecification(
            name="primary",
            duration_ms=etl_config.WINDOW_DURATION_MS,
            stride_ms=etl_config.WINDOW_STRIDE_MS,
        ),
    )
