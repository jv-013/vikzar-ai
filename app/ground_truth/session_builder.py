"""Build a verified synchronized training-session artifact from one CaptureSession."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Callable

from app.config import ground_truth_config

from .alignment import TimestampAlignmentVerifier
from .contracts.capture import CaptureSession, TrainingPhase, TrainingPhaseSegment
from .contracts.output import (
    AlignedTrainingWindow,
    ProvenanceRecord,
    SessionQualityReport,
    VerifiedSynchronizedTrainingSession,
    WindowDisposition,
    WindowQualityResult,
)
from .contracts.synchronization import SynchronizationObservation
from .label_generation import MeasuredEMGLabelGenerator
from .quality_control import GroundTruthQualityController


class GroundTruthSessionBuilder:
    """Transform one immutable capture session into verified ground truth.

    This class is offline-only. It consumes capture evidence already recorded
    by acquisition and never communicates with hardware, changes ETL values,
    trains a model, or estimates muscle activity.
    """

    def __init__(
        self,
        quality_controller: GroundTruthQualityController | None = None,
        label_generator: MeasuredEMGLabelGenerator | None = None,
        alignment_verifier: TimestampAlignmentVerifier | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        """Initialize deterministic ground-truth collaborators.

        Args:
            quality_controller: Optional eligibility-policy implementation.
            label_generator: Optional direct-measurement label generator.
            clock: Timestamp source for output provenance.
        """

        self._quality_controller = quality_controller or GroundTruthQualityController()
        self._label_generator = label_generator or MeasuredEMGLabelGenerator()
        self._alignment_verifier = alignment_verifier or TimestampAlignmentVerifier()
        self._clock = clock

    def build(self, capture: CaptureSession) -> VerifiedSynchronizedTrainingSession:
        """Build an immutable verified session from a single CaptureSession.

        Args:
            capture: Complete acquisition artifact with ETL data and evidence.

        Returns:
            Verified output containing only accepted aligned windows and direct
            EMG labels, plus quality outcomes for every evaluated candidate.
        """

        self._alignment_verifier.verify(capture)
        audit_by_key = {
            (observation.feature_vector_id, observation.group_id): observation
            for observation in capture.synchronization_audit.observations
        }
        recordings_by_group = {recording.group_id: recording for recording in capture.emg_recordings}
        placements_by_device = {record.device_id: record for record in capture.placement_records}

        windows: list[AlignedTrainingWindow] = []
        labels = []
        quality_results: list[WindowQualityResult] = []

        for vector in capture.raw_feature_vectors:
            for group_id, feature_group in vector.groups.items():
                observation = audit_by_key.get((vector.feature_vector_id, group_id))
                phase = self._phase_for_window(capture.phases, feature_group.window_start, feature_group.window_end)
                recording = recordings_by_group.get(group_id)
                result = self._quality_controller.assess(
                    feature_vector_id=vector.feature_vector_id,
                    group_id=group_id,
                    feature_group=feature_group,
                    synchronization=observation,
                    synchronization_tolerance_ms=capture.synchronization_audit.tolerance_ms,
                    phase=phase,
                    emg_recording=recording,
                    placement=(placements_by_device.get(recording.device_id) if recording else None),
                )
                quality_results.append(result)

                if result.disposition is not WindowDisposition.ACCEPTED:
                    continue
                if observation is None or feature_group.muscle is None or phase is None:
                    # Defensive guard: the quality policy already rejects these cases.
                    continue

                aligned_window_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{capture.capture_session_id}:{vector.feature_vector_id}:{group_id}",
                    )
                )
                pod_features = {
                    name: domain
                    for name, domain in (("motion", feature_group.motion), ("pressure", feature_group.pressure))
                    if domain is not None
                }
                window = AlignedTrainingWindow(
                    aligned_window_id=aligned_window_id,
                    source_feature_vector_id=vector.feature_vector_id,
                    group_id=group_id,
                    window_start_ms=feature_group.window_start,
                    window_end_ms=feature_group.window_end,
                    phase_segment_id=phase.segment_id,
                    phase=phase.phase,
                    drill_id=phase.drill_id,
                    drill_protocol_version=phase.drill_protocol_version,
                    smart_pod_features=pod_features,
                    emg_measurements=feature_group.muscle,
                    synchronization=observation,
                )
                windows.append(window)
                labels.extend(
                    self._label_generator.generate(
                        aligned_window_id=aligned_window_id,
                        source_feature_vector_id=vector.feature_vector_id,
                        group_id=group_id,
                        measurements=feature_group.muscle,
                        recording=recordings_by_group[group_id],
                    )
                )

        counts = Counter(result.disposition for result in quality_results)
        generated_at = self._clock()
        quality_report = SessionQualityReport(
            evaluated_at=generated_at,
            total_candidates=len(quality_results),
            accepted_count=counts[WindowDisposition.ACCEPTED],
            questionable_count=counts[WindowDisposition.QUESTIONABLE],
            rejected_count=counts[WindowDisposition.REJECTED],
            results=tuple(quality_results),
        )
        provenance = ProvenanceRecord(
            ground_truth_schema_version=ground_truth_config.GROUND_TRUTH_SCHEMA_VERSION,
            capture_session_schema_version=capture.schema_version,
            capture_session_id=capture.capture_session_id,
            generated_at=generated_at,
            source_sha256=capture.source_sha256,
            synchronization_audit_id=capture.synchronization_audit.audit_id,
        )
        first_vector = capture.raw_feature_vectors[0]
        return VerifiedSynchronizedTrainingSession(
            verified_session_id=str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"verified:{capture.capture_session_id}")
            ),
            capture_session_id=capture.capture_session_id,
            player_id=first_vector.player.player_id,
            session_id=first_vector.session.session_id,
            aligned_windows=tuple(windows),
            labels=tuple(labels),
            quality_report=quality_report,
            provenance=provenance,
        )

    @staticmethod
    def _phase_for_window(
        phases: tuple[TrainingPhaseSegment, ...],
        window_start_ms: float,
        window_end_ms: float,
    ) -> TrainingPhaseSegment | None:
        """Return the phase containing the full UTC-epoch feature window."""

        start = datetime.fromtimestamp(window_start_ms / 1000.0, tz=timezone.utc)
        end = datetime.fromtimestamp(window_end_ms / 1000.0, tz=timezone.utc)
        matching = [phase for phase in phases if phase.started_at <= start and end <= phase.ended_at]
        return matching[0] if len(matching) == 1 else None
