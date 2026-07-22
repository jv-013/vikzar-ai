"""Reusable factories for ground-truth pipeline tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.ground_truth.contracts import (
    CalibrationSession,
    CaptureSession,
    DeviceMetadata,
    EMGRecording,
    SensorPlacementRecord,
    SynchronizationAudit,
    SynchronizationObservation,
    SynchronizationStatus,
    TrainingPhase,
    TrainingPhaseSegment,
)
from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.group_feature_set import GroupFeatureSet
from app.schemas.hardware_provenance import HardwareProvenance
from app.schemas.player import Player
from app.schemas.quality_info import BiomarkerQualityInfo, QualityStatusInfo
from app.schemas.raw_feature_vector import RawFeatureVector
from app.schemas.session import Session

START = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)


def make_capture(
    *,
    status: SynchronizationStatus = SynchronizationStatus.MATCHED,
    alignment_error_ms: float | None = 2.0,
    emg_quality: QualityStatusInfo = QualityStatusInfo.VALID,
    phase: TrainingPhase = TrainingPhase.DRILL,
) -> CaptureSession:
    """Build one complete, minimal capture session for tests."""

    start_ms = START.timestamp() * 1000.0
    end_ms = start_ms + 1000.0
    quality = BiomarkerQualityInfo(status=emg_quality, flags=(), rationale="test quality")
    vector = RawFeatureVector(
        feature_vector_id="rfv-1",
        timestamp=START,
        schema_version="1.0.0",
        source="vikzar_etl_v1",
        player=Player(player_id="player-1", age=22, sex="female", dominant_leg="right", position="midfielder"),
        session=Session(session_id="training-1"),
        hardware=HardwareProvenance(firmware_revision="fw-1", hardware_revision="hw-1", protocol_version="1"),
        groups={
            "left_lower_limb": GroupFeatureSet(
                window_start=start_ms,
                window_end=end_ms,
                motion=DomainBiomarkers(
                    biomarkers={"peak_resultant_acceleration": 4.0},
                    quality={"peak_resultant_acceleration": quality},
                ),
                muscle=DomainBiomarkers(
                    biomarkers={"quadriceps_rms": 0.3, "hamstring_rms": 0.2},
                    quality={"quadriceps_rms": quality, "hamstring_rms": quality},
                ),
            )
        },
    )
    observation = SynchronizationObservation(
        feature_vector_id="rfv-1",
        group_id="left_lower_limb",
        status=status,
        primary_timestamp_ms=start_ms,
        emg_timestamp_ms=(
            start_ms + alignment_error_ms
            if status is SynchronizationStatus.MATCHED and alignment_error_ms is not None
            else None
        ),
        alignment_error_ms=alignment_error_ms if status is SynchronizationStatus.MATCHED else None,
    )
    drill_fields = (
        {"drill_id": "planned_cut", "drill_protocol_version": "1.0"}
        if phase is TrainingPhase.DRILL
        else {}
    )
    segment = TrainingPhaseSegment(
        segment_id="segment-1",
        phase=phase,
        started_at=START - timedelta(seconds=1),
        ended_at=START + timedelta(seconds=2),
        **drill_fields,
    )
    return CaptureSession(
        capture_session_id="capture-1",
        schema_version="1.0.0",
        captured_at=START,
        raw_feature_vectors=(vector,),
        emg_recordings=(
            EMGRecording(
                recording_id="emg-recording-1",
                device_id="left-emg",
                group_id="left_lower_limb",
                sampling_rate_hz=1000,
                amplitude_unit="volts",
                normalization_method="raw",
                source_uri="capture://emg-1",
                source_sha256="a" * 64,
            ),
        ),
        synchronization_audit=SynchronizationAudit(
            audit_id="audit-1",
            clock_reference="UTC epoch milliseconds",
            tolerance_ms=5.0,
            observations=(observation,),
        ),
        placement_records=(
            SensorPlacementRecord(
                device_id="left-pod",
                group_id="left_lower_limb",
                body_side="left",
                anatomical_location="left shin",
                orientation_description="long axis vertical",
                fixation_description="strap",
                placement_verified=True,
                verified_by="operator-1",
            ),
            SensorPlacementRecord(
                device_id="left-emg",
                group_id="left_lower_limb",
                body_side="left",
                anatomical_location="left thigh",
                orientation_description="parallel to fibres",
                fixation_description="elastic strap",
                channel_to_muscle={"quadriceps": "vastus lateralis", "hamstring": "biceps femoris"},
                placement_verified=True,
                verified_by="operator-1",
            ),
        ),
        devices=(
            DeviceMetadata(device_id="left-pod", device_type="smart_pod", serial_number="pod-1", firmware_revision="fw-1", hardware_revision="hw-1"),
            DeviceMetadata(device_id="left-emg", device_type="emg_strap", serial_number="emg-1", firmware_revision="fw-1", hardware_revision="hw-1"),
        ),
        calibration_sessions=(
            CalibrationSession(
                calibration_id="cal-1",
                started_at=START - timedelta(minutes=5),
                ended_at=START - timedelta(minutes=4),
                procedure="approved reference contraction",
                normalization_method="raw",
                operator_id="operator-1",
            ),
        ),
        phases=(segment,),
        source_sha256={"capture_manifest": "b" * 64},
    )
