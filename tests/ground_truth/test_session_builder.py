"""Integration tests for building verified synchronized training sessions."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ground_truth import GroundTruthSessionBuilder
from app.ground_truth.contracts import SynchronizationStatus, TrainingPhase, WindowDisposition
from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.quality_info import QualityStatusInfo

from .helpers import make_capture


def test_builds_direct_measured_emg_labels_from_accepted_drill_window() -> None:
    """Accepted capture evidence produces aligned features and measured labels only."""

    builder = GroundTruthSessionBuilder(clock=lambda: datetime(2026, 7, 19, tzinfo=timezone.utc))
    output = builder.build(make_capture())

    assert len(output.aligned_windows) == 1
    assert output.aligned_windows[0].smart_pod_features["motion"].biomarkers["peak_resultant_acceleration"] == 4.0
    assert {label.metric_name for label in output.labels} == {"quadriceps_rms", "hamstring_rms"}
    assert {label.amplitude_unit for label in output.labels} == {"volts"}
    assert output.quality_report.accepted_count == 1
    assert output.quality_report.rejected_count == 0


def test_rejects_unmatched_capture_without_fabricating_labels() -> None:
    """Timed-out synchronization remains traceable but never becomes ground truth."""

    output = GroundTruthSessionBuilder().build(
        make_capture(status=SynchronizationStatus.TIMED_OUT, alignment_error_ms=None)
    )

    assert output.aligned_windows == ()
    assert output.labels == ()
    assert output.quality_report.results[0].disposition is WindowDisposition.REJECTED
    assert "synchronization_status_timed_out" in output.quality_report.results[0].reasons


def test_rejects_questionable_emg_and_non_drill_phase_from_training_labels() -> None:
    """Questionable EMG and warm-up data are retained in QC but excluded from labels."""

    output = GroundTruthSessionBuilder().build(
        make_capture(emg_quality=QualityStatusInfo.QUESTIONABLE, phase=TrainingPhase.WARM_UP)
    )

    assert output.aligned_windows == ()
    result = output.quality_report.results[0]
    assert result.disposition is WindowDisposition.REJECTED
    assert "etl_questionable_emg_biomarker" in result.reasons
    assert "phase_warm_up_not_training_label_eligible" in result.reasons


def test_rejects_alignment_beyond_session_recorded_tolerance() -> None:
    """The audit tolerance controls eligibility rather than a hidden threshold."""

    output = GroundTruthSessionBuilder().build(make_capture(alignment_error_ms=5.1))

    assert output.aligned_windows == ()
    assert "synchronization_tolerance_exceeded" in output.quality_report.results[0].reasons


def test_rejects_an_empty_measured_emg_domain() -> None:
    """An empty EMG payload cannot become an accepted window without labels."""

    capture = make_capture()
    vector = capture.raw_feature_vectors[0]
    group = vector.groups["left_lower_limb"].model_copy(
        update={"muscle": DomainBiomarkers(biomarkers={}, quality={})}
    )
    capture = capture.model_copy(
        update={
            "raw_feature_vectors": (
                vector.model_copy(update={"groups": {"left_lower_limb": group}}),
            )
        }
    )

    output = GroundTruthSessionBuilder().build(capture)

    assert output.aligned_windows == ()
    assert output.quality_report.results[0].disposition is WindowDisposition.REJECTED
    assert "measured_emg_biomarkers_empty" in output.quality_report.results[0].reasons
