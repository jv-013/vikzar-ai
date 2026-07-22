"""Factories for synthetic Phase 2 outputs used by Dataset Builder tests."""

from __future__ import annotations

from app.ground_truth import GroundTruthSessionBuilder
from app.ground_truth.contracts import VerifiedSynchronizedTrainingSession

from tests.ground_truth.helpers import make_capture


def make_verified_session(
    *,
    capture_session_id: str = "capture-1",
    player_id: str = "player-1",
    session_id: str = "training-1",
) -> VerifiedSynchronizedTrainingSession:
    """Create ordinary verified-session evidence; no production code sees its origin."""

    capture = make_capture()
    vector = capture.raw_feature_vectors[0]
    vector = vector.model_copy(
        update={
            "player": vector.player.model_copy(update={"player_id": player_id}),
            "session": vector.session.model_copy(update={"session_id": session_id}),
        }
    )
    return GroundTruthSessionBuilder().build(
        capture.model_copy(
            update={
                "capture_session_id": capture_session_id,
                "raw_feature_vectors": (vector,),
            }
        )
    )
