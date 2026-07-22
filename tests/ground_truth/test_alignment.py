"""Timestamp-audit integrity and capture-consistency tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ground_truth import GroundTruthSessionBuilder
from app.ground_truth.contracts import SynchronizationAudit, SynchronizationObservation, SynchronizationStatus
from app.ground_truth.exceptions import CaptureSessionError

from .helpers import make_capture


def test_builder_rejects_internally_inconsistent_matched_timestamps() -> None:
    """A claimed audit error must equal the observed timestamp difference."""

    capture = make_capture()
    observation = capture.synchronization_audit.observations[0].model_copy(
        update={"alignment_error_ms": 1.0}
    )
    invalid_audit = capture.synchronization_audit.model_copy(update={"observations": (observation,)})

    with pytest.raises(CaptureSessionError, match="does not match"):
        GroundTruthSessionBuilder().build(capture.model_copy(update={"synchronization_audit": invalid_audit}))


def test_capture_rejects_audit_observation_for_unknown_group() -> None:
    """The audit may omit a candidate for QC, but never invent a candidate."""

    capture = make_capture()
    unknown = SynchronizationObservation(
        feature_vector_id="rfv-1",
        group_id="right_lower_limb",
        status=SynchronizationStatus.TIMED_OUT,
        primary_timestamp_ms=1.0,
    )
    with pytest.raises(ValidationError, match="unknown feature vector or group"):
        capture.model_validate(
            capture.model_dump(mode="python")
            | {"synchronization_audit": SynchronizationAudit(
                audit_id="audit-unknown",
                clock_reference="UTC",
                tolerance_ms=5.0,
                observations=(unknown,),
            )}
        )
