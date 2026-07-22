"""Offline verification of capture-side timestamp-alignment evidence."""

from __future__ import annotations

import math

from .contracts.capture import CaptureSession
from .contracts.synchronization import SynchronizationStatus
from .exceptions import CaptureSessionError


class TimestampAlignmentVerifier:
    """Validate that a recorded synchronization audit is internally coherent.

    This verifier does not align, interpolate, or infer timestamps.  It only
    checks the arithmetic evidence already captured by acquisition.
    """

    _ERROR_ABSOLUTE_TOLERANCE_MS = 0.001

    def verify(self, capture: CaptureSession) -> None:
        """Raise when a claimed matched timestamp lacks coherent evidence."""

        for observation in capture.synchronization_audit.observations:
            if observation.status is not SynchronizationStatus.MATCHED:
                continue

            assert observation.emg_timestamp_ms is not None
            assert observation.alignment_error_ms is not None
            expected_error = abs(observation.primary_timestamp_ms - observation.emg_timestamp_ms)
            if not math.isclose(
                observation.alignment_error_ms,
                expected_error,
                abs_tol=self._ERROR_ABSOLUTE_TOLERANCE_MS,
            ):
                raise CaptureSessionError(
                    "Synchronization alignment error does not match its recorded timestamps "
                    f"for {observation.feature_vector_id}/{observation.group_id}."
                )
