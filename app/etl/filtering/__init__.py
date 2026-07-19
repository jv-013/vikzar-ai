"""
Filtering package.

Stage 5 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/FILTERING_DESIGN.md.

FilteredFrame is exported for use elsewhere within app/etl (e.g. the
future Sliding Window stage). It must never be imported outside app/etl.
"""

from .defaults import default_signal_filter_factories
from .filterer import Filterer, FilteredFrameConsumer
from .frame import FilteredFrame
from .reading import FilteredReading
from .signal_filter import EMGFilter, FSR402Filter, IMUFilter, SignalFilter

__all__ = [
    "Filterer",
    "FilteredFrameConsumer",
    "FilteredFrame",
    "FilteredReading",
    "SignalFilter",
    "IMUFilter",
    "EMGFilter",
    "FSR402Filter",
    "default_signal_filter_factories",
]
