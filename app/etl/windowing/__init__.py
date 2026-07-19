"""
Windowing package.

Stage 6 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/WINDOWING_DESIGN.md.

Window is exported for use elsewhere within app/etl (e.g. the future
Feature Extraction stage). It must never be imported outside app/etl.
"""

from .defaults import default_window_specifications
from .window import Window
from .window_specification import WindowSpecification
from .windower import WindowConsumer, Windower

__all__ = [
    "Windower",
    "WindowConsumer",
    "Window",
    "WindowSpecification",
    "default_window_specifications",
]
