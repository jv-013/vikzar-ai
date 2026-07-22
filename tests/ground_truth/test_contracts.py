"""Tests for immutable ground-truth capture contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ground_truth.contracts import SynchronizationAudit, SynchronizationObservation, SynchronizationStatus

from .helpers import make_capture


def test_capture_session_is_immutable_and_contains_calibration_metadata() -> None:
    """A capture is the sole immutable source passed to Phase 2."""

    capture = make_capture()

    assert capture.calibration_sessions[0].calibration_id == "cal-1"
    with pytest.raises(ValidationError):
        capture.capture_session_id = "different"  # type: ignore[misc]


def test_matched_synchronization_requires_timestamp_and_error_evidence() -> None:
    """A claimed match without timing evidence is invalid at capture construction."""

    with pytest.raises(ValidationError):
        SynchronizationObservation(
            feature_vector_id="rfv-1",
            group_id="left_lower_limb",
            status=SynchronizationStatus.MATCHED,
            primary_timestamp_ms=1.0,
        )


def test_audit_rejects_duplicate_vector_group_evidence() -> None:
    """One candidate must have exactly one audit outcome."""

    observation = SynchronizationObservation(
        feature_vector_id="rfv-1",
        group_id="left_lower_limb",
        status=SynchronizationStatus.MATCHED,
        primary_timestamp_ms=1.0,
        emg_timestamp_ms=2.0,
        alignment_error_ms=1.0,
    )
    with pytest.raises(ValidationError):
        SynchronizationAudit(
            audit_id="audit-1",
            clock_reference="UTC",
            tolerance_ms=5.0,
            observations=(observation, observation),
        )
