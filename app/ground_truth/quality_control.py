"""Quality decisions for measured, synchronized training windows."""

from __future__ import annotations

from app.schemas.group_feature_set import GroupFeatureSet
from app.schemas.quality_info import QualityStatusInfo

from .contracts.capture import EMGRecording, SensorPlacementRecord, TrainingPhaseSegment
from .contracts.output import WindowDisposition, WindowQualityResult
from .contracts.synchronization import SynchronizationObservation, SynchronizationStatus


class GroundTruthQualityController:
    """Apply transparent, non-imputing eligibility rules to a candidate window."""

    def assess(
        self,
        *,
        feature_vector_id: str,
        group_id: str,
        feature_group: GroupFeatureSet,
        synchronization: SynchronizationObservation | None,
        synchronization_tolerance_ms: float,
        phase: TrainingPhaseSegment | None,
        emg_recording: EMGRecording | None,
        placement: SensorPlacementRecord | None,
    ) -> WindowQualityResult:
        """Return the documented eligibility outcome for one ETL group window.

        Args:
            feature_vector_id: ETL source identifier for the candidate.
            group_id: Synchronization-group identifier for the candidate.
            feature_group: Lossless ETL features and their annotations.
            synchronization: Capture-side timing evidence, if available.
            synchronization_tolerance_ms: Session-recorded allowed timing error.
            phase: Training segment covering the whole feature window.
            emg_recording: EMG acquisition metadata mapped to this group.
            placement: Verified sensor placement mapped to this group.

        Returns:
            Explainable accepted, questionable, or rejected disposition.
        """

        rejected: list[str] = []
        questionable: list[str] = []

        if synchronization is None:
            rejected.append("synchronization_audit_missing")
        elif synchronization.status is not SynchronizationStatus.MATCHED:
            rejected.append(f"synchronization_status_{synchronization.status.value}")
        elif synchronization.alignment_error_ms is None:
            rejected.append("synchronization_alignment_error_missing")
        elif synchronization.alignment_error_ms > synchronization_tolerance_ms:
            rejected.append("synchronization_tolerance_exceeded")

        if feature_group.muscle is None:
            rejected.append("measured_emg_domain_absent")
        elif not feature_group.muscle.biomarkers:
            rejected.append("measured_emg_biomarkers_empty")
        else:
            statuses = [quality.status for quality in feature_group.muscle.quality.values()]
            if any(status is QualityStatusInfo.REJECTED for status in statuses):
                rejected.append("etl_rejected_emg_biomarker")
            elif any(status is QualityStatusInfo.QUESTIONABLE for status in statuses):
                questionable.append("etl_questionable_emg_biomarker")

        if phase is None:
            rejected.append("training_phase_missing")
        elif phase.phase.value != "drill":
            rejected.append(f"phase_{phase.phase.value}_not_training_label_eligible")

        if emg_recording is None:
            rejected.append("emg_recording_metadata_missing")
        if placement is None:
            rejected.append("sensor_placement_record_missing")
        elif not placement.placement_verified:
            rejected.append("sensor_placement_not_verified")

        if rejected:
            disposition = WindowDisposition.REJECTED
            reasons = tuple(rejected + questionable)
        elif questionable:
            disposition = WindowDisposition.QUESTIONABLE
            reasons = tuple(questionable)
        else:
            disposition = WindowDisposition.ACCEPTED
            reasons = ()

        return WindowQualityResult(
            feature_vector_id=feature_vector_id,
            group_id=group_id,
            disposition=disposition,
            reasons=reasons,
        )
