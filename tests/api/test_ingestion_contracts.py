"""Wire-format tests for the ingestion Cloud Function payloads
(BACKEND_SPECIFICATION.md §21) — verifies field names/shape match the
Callable functions' own contract exactly (`vikzar-app/functions/src/contracts/types.ts`)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.api.ingestion_contracts import (
    CompleteSessionPayload,
    ContributingFactorPayload,
    IngestLiveTickPayload,
    LiveTickMetrics,
    RecommendationPayload,
    StartSessionPayload,
    SubmitAlertPayload,
    SubmitReportPayload,
    SummaryMetricsPayload,
)


def test_start_session_to_wire_matches_section_21_3_field_names() -> None:
    payload = StartSessionPayload(
        session_id="s1",
        player_id="p1",
        team_id="t1",
        org_id="o1",
        type="training",
        device_ids=("SP-1", "EB-1"),
        started_at=datetime(2026, 7, 19, 14, 30, tzinfo=timezone.utc),
    )
    wire = payload.to_wire()
    assert wire == {
        "sessionId": "s1",
        "playerId": "p1",
        "teamId": "t1",
        "orgId": "o1",
        "type": "training",
        "deviceIds": ["SP-1", "EB-1"],
        "startedAt": "2026-07-19T14:30:00+00:00",
    }


def test_start_session_omits_absent_optional_fields() -> None:
    payload = StartSessionPayload(
        session_id="s1",
        player_id="p1",
        type="match",
        device_ids=("SP-1",),
        started_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )
    wire = payload.to_wire()
    assert "teamId" not in wire
    assert "orgId" not in wire


def test_ingest_live_tick_to_wire_matches_section_21_4_field_names() -> None:
    payload = IngestLiveTickPayload(
        session_id="s1",
        player_id="p1",
        sequence_number=412,
        tick_timestamp=datetime(2026, 7, 19, 14, 36, 52, tzinfo=timezone.utc),
        connection_status="connected",
        metrics=LiveTickMetrics(
            current_load=47.2,
            cumulative_impacts=63,
            risk_score=0.18,
            risk_level="low",
        ),
    )
    wire = payload.to_wire()
    assert wire["sessionId"] == "s1"
    assert wire["sequenceNumber"] == 412
    assert wire["connectionStatus"] == "connected"
    assert wire["metrics"] == {
        "currentLoad": 47.2,
        "cumulativeImpacts": 63,
        "riskScore": 0.18,
        "riskLevel": "low",
    }


def test_ingest_live_tick_includes_additive_risk_engine_subscores() -> None:
    payload = IngestLiveTickPayload(
        session_id="s1",
        player_id="p1",
        sequence_number=1,
        tick_timestamp=datetime(2026, 7, 19, tzinfo=timezone.utc),
        connection_status="connected",
        metrics=LiveTickMetrics(
            current_load=1.0,
            cumulative_impacts=0,
            risk_score=0.1,
            risk_level="low",
            confidence=0.9,
            fatigue_level="elevated",
        ),
    )
    wire = payload.to_wire()
    assert wire["metrics"]["confidence"] == 0.9
    assert wire["metrics"]["fatigueLevel"] == "elevated"
    assert "workloadRatio" not in wire["metrics"]


def test_ingest_live_tick_omits_device_rssi_and_capture_phase_when_unset() -> None:
    payload = IngestLiveTickPayload(
        session_id="s1",
        player_id="p1",
        sequence_number=1,
        tick_timestamp=datetime(2026, 7, 19, tzinfo=timezone.utc),
        connection_status="connected",
        metrics=LiveTickMetrics(
            current_load=1.0, cumulative_impacts=0, risk_score=0.1, risk_level="low"
        ),
    )
    wire = payload.to_wire()
    assert "deviceRssi" not in wire
    assert "capturePhase" not in wire


def test_ingest_live_tick_includes_device_rssi_and_capture_phase_when_set() -> None:
    payload = IngestLiveTickPayload(
        session_id="s1",
        player_id="p1",
        sequence_number=1,
        tick_timestamp=datetime(2026, 7, 19, tzinfo=timezone.utc),
        connection_status="connected",
        metrics=LiveTickMetrics(
            current_load=1.0, cumulative_impacts=0, risk_score=0.1, risk_level="low"
        ),
        device_rssi={"SP-1": -58.0},
        capture_phase="recording",
    )
    wire = payload.to_wire()
    assert wire["deviceRssi"] == {"SP-1": -58.0}
    assert wire["capturePhase"] == "recording"


def test_complete_session_to_wire_matches_section_21_5_field_names() -> None:
    payload = CompleteSessionPayload(
        session_id="s1",
        ended_at=datetime(2026, 7, 19, 16, 2, tzinfo=timezone.utc),
        duration_seconds=5531,
        status="completed",
        summary_metrics=SummaryMetricsPayload(
            total_impacts=288,
            peak_impact_force=62.4,
            average_load=41.9,
            cumulative_load_index=2317.6,
            overall_risk_score=0.24,
            risk_level="low",
            risk_factors=(),
        ),
        data_completeness=0.997,
        pipeline_version="etl-2.3.1+ml-1.7.0+risk-1.2.0",
    )
    wire = payload.to_wire()
    assert wire["durationSeconds"] == 5531
    assert wire["dataCompleteness"] == 0.997
    assert wire["summaryMetrics"]["totalImpacts"] == 288
    assert wire["summaryMetrics"]["riskFactors"] == []
    assert "muscleFatigueIndex" not in wire["summaryMetrics"]
    assert "rawDataStoragePath" not in wire


def test_submit_alert_to_wire_matches_section_21_6_field_names() -> None:
    payload = SubmitAlertPayload(
        session_id="s1",
        player_id="p1",
        team_id="t1",
        severity="warning",
        type="high_impact",
        message="A high-magnitude impact was recorded.",
        triggered_at=datetime(2026, 7, 19, 15, 12, 44, tzinfo=timezone.utc),
        metrics_snapshot={"impactForce": 58.9},
        contributing_factors=(
            ContributingFactorPayload(component="fatigue", score=41.0, weight=0.3, contribution=12.3),
        ),
        recommendations=(
            RecommendationPayload(code="rest", priority="high", message="Consider a rest day."),
        ),
    )
    wire = payload.to_wire()
    assert wire["severity"] == "warning"
    assert wire["type"] == "high_impact"
    assert wire["contributingFactors"] == [
        {"component": "fatigue", "score": 41.0, "weight": 0.3, "contribution": 12.3}
    ]
    assert wire["recommendations"] == [
        {"code": "rest", "priority": "high", "message": "Consider a rest day."}
    ]


def test_submit_alert_omits_empty_factor_and_recommendation_lists() -> None:
    payload = SubmitAlertPayload(
        session_id="s1",
        player_id="p1",
        severity="info",
        type="low_battery",
        message="Battery low.",
        triggered_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )
    wire = payload.to_wire()
    assert "contributingFactors" not in wire
    assert "recommendations" not in wire


def test_submit_report_to_wire_matches_section_21_7_field_names() -> None:
    payload = SubmitReportPayload(
        session_id="s1",
        player_id="p1",
        generated_at=datetime(2026, 7, 19, 16, 3, 5, tzinfo=timezone.utc),
        summary={"overallRiskScore": 0.24, "riskLevel": "low"},
    )
    wire = payload.to_wire()
    assert wire["generatedAt"] == "2026-07-19T16:03:05+00:00"
    assert wire["summary"] == {"overallRiskScore": 0.24, "riskLevel": "low"}
    assert "storagePath" not in wire
