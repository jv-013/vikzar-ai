"""
Calibration.

Stage 4 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/CALIBRATION_DESIGN.md).

Converts each SynchronizedFrame's raw, device-native channel values into
CalibratedChannel values, per synchronization group, using deterministic
CalibrationFunction strategies. Never merges or compares across groups;
never computes derived features; never performs filtering or AI
inference.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Mapping

from app.etl.synchronization import SynchronizedFrame
from app.etl.validation import ValidatedPacket

from .frame import CalibratedFrame
from .function import CalibrationFunction
from .reading import CalibratedReading

logger = logging.getLogger(__name__)

CalibratedFrameConsumer = Callable[[CalibratedFrame], None]
"""Invoked with each CalibratedFrame as it is emitted."""


class Calibrator:
    """
    Converts SynchronizedFrames into CalibratedFrames.

    Purpose
        Apply per-channel CalibrationFunctions to every reading in a
        SynchronizedFrame, independently per synchronization group,
        preserving group_id, reference_timestamp, and sync_status
        unchanged (Decision 022).

    Idempotency guarantee
        Calibration is idempotent: it is a pure function of its input,
        with no side effects or mutation, so calling it twice on the
        same SynchronizedFrame produces identical output. handle() only
        ever accepts a SynchronizedFrame — CalibratedFrame is a
        structurally distinct type with no overlapping shape, so there
        is no code path by which a CalibratedFrame could be silently
        re-accepted. This is enforced mechanically, not just claimed in
        this docstring: handle() raises TypeError immediately if given
        anything else. That check is intentionally outside handle()'s
        own try/except — unlike a corrupted packet or an unmatched
        timing window (normal, expected occurrences in a live sensor
        stream that every prior ETL stage degrades gracefully from), a
        type violation here means the pipeline itself is wired
        incorrectly. That is a programming error, not a data-quality
        one, and should fail loudly and immediately rather than be
        silently logged and ignored.
    """

    def __init__(
        self,
        calibration_functions: Mapping[str, CalibrationFunction],
        on_calibrated: CalibratedFrameConsumer,
    ) -> None:
        """
        Initialize the calibrator.

        Args:
            calibration_functions: CalibrationFunction to apply, keyed
                by channel name (e.g. "accel_x"). A channel present in
                a packet's raw_channels but absent from this mapping is
                skipped and logged, not calibrated with a guessed
                default (see defaults.default_calibration_functions).
            on_calibrated: Callback invoked with each emitted
                CalibratedFrame.
        """
        self._calibration_functions: Dict[str, CalibrationFunction] = dict(calibration_functions)
        self._on_calibrated = on_calibrated

    def handle(self, frame: SynchronizedFrame) -> None:
        """
        Calibrate a single SynchronizedFrame.

        This is the entry point wired as Synchronizer's on_synchronized
        callback. Data-quality problems (e.g. an unconfigured channel)
        are logged and degraded gracefully; a wrong input type is a
        wiring bug and raises immediately. See the idempotency
        guarantee above.

        Args:
            frame: The frame to calibrate.

        Raises:
            TypeError: If frame is not a SynchronizedFrame.
        """
        if not isinstance(frame, SynchronizedFrame):
            raise TypeError(
                f"Calibrator.handle() only accepts SynchronizedFrame; received "
                f"{type(frame).__name__}. Calibration is idempotent — a "
                f"CalibratedFrame (or any other object) must never be passed "
                f"back into Calibration."
            )
        try:
            self._handle(frame)
        except Exception:
            logger.exception(
                "calibrator.unexpected_error",
                extra={"group_id": frame.group_id},
            )

    def _handle(self, frame: SynchronizedFrame) -> None:
        readings: Dict[str, CalibratedReading] = {}
        for role, packet in frame.packets.items():
            if packet is None:
                continue
            readings[role] = self._calibrate_reading(packet)

        calibrated_frame = CalibratedFrame(
            group_id=frame.group_id,
            reference_timestamp=frame.reference_timestamp,
            sync_status=frame.sync_status,
            readings=readings,
        )
        self._on_calibrated(calibrated_frame)

    def _calibrate_reading(self, packet: ValidatedPacket) -> CalibratedReading:
        calibrated_channels = {}
        for channel_name, raw_value in packet.raw_channels.items():
            calibration_function = self._calibration_functions.get(channel_name)
            if calibration_function is None:
                logger.warning(
                    "calibrator.unconfigured_channel",
                    extra={"channel_name": channel_name, "device_id": packet.device_id},
                )
                continue
            calibrated_channels[channel_name] = calibration_function.calibrate(raw_value)

        return CalibratedReading(
            calibrated_channels=calibrated_channels,
            device_id=packet.device_id,
            sequence_number=packet.sequence_number,
            device_timestamp_ms=packet.device_timestamp_ms,
            received_at=packet.received_at,
            protocol_version=packet.protocol_version,
        )
