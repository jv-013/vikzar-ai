"""Integration tests across existing runtime metadata, Phase 8, and Phase 9."""

from __future__ import annotations

from app.risk_engine import RiskAssessmentRequest
from app.schemas.player import Player
from app.schemas.session import Session


def test_existing_player_session_and_phase_eight_contracts_follow_normal_path(
    risk_engine,
    low_risk_request,
) -> None:
    request = RiskAssessmentRequest.from_runtime(
        predictions=low_risk_request.predictions,
        player=Player(
            player_id="player-001",
            age=24,
            sex="male",
            dominant_leg="right",
            position="midfielder",
        ),
        session=Session(
            session_id="session-001",
            drill="cutting",
            training_intensity="moderate",
            fatigue_level=20,
        ),
        baseline=low_risk_request.baseline,
    )

    assessment = risk_engine.assess(request)

    assert assessment.provenance.player_id == "player-001"
    assert assessment.provenance.session_id == "session-001"
    assert assessment.provenance.prediction_checksums == tuple(
        prediction.checksum
        for prediction in sorted(
            low_risk_request.predictions,
            key=lambda item: (
                item.metadata.source_timestamp,
                item.metadata.window_end,
                item.metadata.group_id,
                item.prediction_id,
            ),
        )
    )
