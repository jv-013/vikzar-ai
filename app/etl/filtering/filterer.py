"""
Filtering.

Stage 5 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/FILTERING_DESIGN.md).

Reduces measurement noise in each SynchronizedFrame's calibrated channel
values, per synchronization group, using deterministic, stateful
SignalFilter strategies. Never merges or compares across groups; never
computes derived features; never performs sliding-window buffering or
AI inference.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Mapping, Optional, Tuple

from app.etl.calibration import CalibratedChannel, CalibratedFrame, CalibratedReading

from .frame import FilteredFrame
from .reading import FilteredReading
from .signal_filter import SignalFilter

logger = logging.getLogger(__name__)

FilteredFrameConsumer = Callable[[FilteredFrame], None]
"""Invoked with each FilteredFrame as it is emitted."""


class Filterer:
    """
    Converts CalibratedFrames into FilteredFrames.

    Purpose
        Apply per-channel SignalFilters to every reading in a
        CalibratedFrame, independently per synchronization group,
        preserving group_id, reference_timestamp, and sync_status
        unchanged (Decision 022).

    State isolation
        Each (group_id, channel_name) pair gets its own SignalFilter
        instance, lazily created on first use and reused for every
        subsequent frame from that group. Instances are never shared
        across groups (no cross-group state) or across channels within
        a group (preserves each channel's own temporal history,
        uncontaminated by any other channel's values).

    Idempotency — a real difference from Calibration
        Calibration is a pure function: feeding the same
        SynchronizedFrame twice produces identical output, so its
        idempotency guard exists only to catch wiring bugs.
        Filtering is not idempotent in that sense — because
        SignalFilter instances hold state, feeding the same
        CalibratedFrame twice would produce genuinely wrong output the
        second time (the filter would treat it as a new sample
        arriving after itself, corrupting that channel's history for
        every frame after it). handle() still only ever accepts a
        CalibratedFrame and raises TypeError immediately, outside the
        internal try/except, for anything else — the same
        fail-loud-on-wiring-bugs discipline as Calibration — but this
        guard only catches a wrong *type*. The stronger guarantee that
        each frame arrives exactly once, in order, per group, is not
        something Filtering enforces itself; it relies on the existing
        synchronous, single-threaded, no-queues pipeline discipline
        every prior stage already depends on for its own state.
    """

    def __init__(
        self,
        filter_factory: Mapping[str, Callable[[], SignalFilter]],
        on_filtered: FilteredFrameConsumer,
    ) -> None:
        """
        Initialize the filterer.

        Args:
            filter_factory: Zero-argument SignalFilter factory, keyed
                by channel name (e.g. "accel_x"). A channel present in
                a reading's calibrated_channels but absent from this
                mapping is skipped and logged, not filtered with a
                guessed default (see defaults.default_signal_filter_factories).
            on_filtered: Callback invoked with each emitted FilteredFrame.
        """
        self._filter_factory: Dict[str, Callable[[], SignalFilter]] = dict(filter_factory)
        self._on_filtered = on_filtered
        self._filters: Dict[Tuple[str, str], SignalFilter] = {}

    def handle(self, frame: CalibratedFrame) -> None:
        """
        Filter a single CalibratedFrame.

        This is the entry point wired as Calibrator's on_calibrated
        callback. Data-quality problems (e.g. an unconfigured channel)
        are logged and degraded gracefully; a wrong input type is a
        wiring bug and raises immediately. See the idempotency note
        above.

        Args:
            frame: The frame to filter.

        Raises:
            TypeError: If frame is not a CalibratedFrame.
        """
        if not isinstance(frame, CalibratedFrame):
            raise TypeError(
                f"Filterer.handle() only accepts CalibratedFrame; received "
                f"{type(frame).__name__}. A FilteredFrame (or any other "
                f"object) must never be passed back into Filtering — unlike "
                f"Calibration, Filtering's per-channel state means "
                f"reprocessing a frame would silently corrupt that "
                f"channel's filter history for every frame after it."
            )
        try:
            self._handle(frame)
        except Exception:
            logger.exception(
                "filterer.unexpected_error",
                extra={"group_id": frame.group_id},
            )

    def _handle(self, frame: CalibratedFrame) -> None:
        readings: Dict[str, FilteredReading] = {}
        for role, reading in frame.readings.items():
            readings[role] = self._filter_reading(frame.group_id, reading)

        filtered_frame = FilteredFrame(
            group_id=frame.group_id,
            reference_timestamp=frame.reference_timestamp,
            sync_status=frame.sync_status,
            readings=readings,
        )
        self._on_filtered(filtered_frame)

    def _filter_reading(self, group_id: str, reading: CalibratedReading) -> FilteredReading:
        filtered_channels: Dict[str, CalibratedChannel] = {}
        for channel_name, calibrated_channel in reading.calibrated_channels.items():
            signal_filter = self._get_or_create_filter(group_id, channel_name)
            if signal_filter is None:
                logger.warning(
                    "filterer.unconfigured_channel",
                    extra={"channel_name": channel_name, "device_id": reading.device_id},
                )
                continue
            filtered_value = signal_filter.filter(calibrated_channel.value)
            filtered_channels[channel_name] = CalibratedChannel(
                value=filtered_value, unit=calibrated_channel.unit
            )

        return FilteredReading(
            filtered_channels=filtered_channels,
            device_id=reading.device_id,
            sequence_number=reading.sequence_number,
            device_timestamp_ms=reading.device_timestamp_ms,
            received_at=reading.received_at,
            protocol_version=reading.protocol_version,
        )

    def _get_or_create_filter(self, group_id: str, channel_name: str) -> Optional[SignalFilter]:
        key = (group_id, channel_name)
        existing = self._filters.get(key)
        if existing is not None:
            return existing

        factory = self._filter_factory.get(channel_name)
        if factory is None:
            return None

        created = factory()
        self._filters[key] = created
        return created
