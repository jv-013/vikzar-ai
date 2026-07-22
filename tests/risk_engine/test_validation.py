"""Strict Phase 8 provenance and metadata failure-path tests."""

from __future__ import annotations

import pytest

from app.risk_engine.exceptions import RiskInputError
from tests.risk_engine.helpers import LEFT_GROUP, make_request


def test_mismatched_player_or_session_is_rejected(
    risk_engine,
    low_risk_request,
) -> None:
    bad_player = low_risk_request.model_copy(
        update={
            "player": low_risk_request.player.model_copy(
                update={"player_id": "other-player"}
            )
        }
    )
    with pytest.raises(RiskInputError):
        risk_engine.assess(bad_player)

    bad_session = low_risk_request.model_copy(
        update={
            "session": low_risk_request.session.model_copy(
                update={"session_id": "other-session"}
            )
        }
    )
    with pytest.raises(RiskInputError):
        risk_engine.assess(bad_session)


def test_mixed_model_lineage_is_rejected(risk_engine, low_risk_request) -> None:
    predictions = list(low_risk_request.predictions)
    changed_metadata = predictions[-1].metadata.model_copy(
        update={"model_id": "other-production-model"}
    )
    predictions[-1] = predictions[-1].model_copy(
        update={"metadata": changed_metadata}
    )
    request = low_risk_request.model_copy(
        update={"predictions": tuple(predictions)}
    )

    with pytest.raises(RiskInputError):
        risk_engine.assess(request)


def test_tampered_prediction_checksum_is_rejected(
    risk_engine,
    low_risk_request,
) -> None:
    predictions = list(low_risk_request.predictions)
    predictions[0] = predictions[0].model_copy(update={"checksum": "0" * 64})
    request = low_risk_request.model_copy(
        update={"predictions": tuple(predictions)}
    )

    with pytest.raises(RiskInputError):
        risk_engine.assess(request)


def test_missing_bilateral_cohort_is_rejected(risk_engine) -> None:
    request = make_request()
    left_only = tuple(
        prediction
        for prediction in request.predictions
        if prediction.metadata.group_id == LEFT_GROUP
    )
    request = request.model_copy(update={"predictions": left_only})

    with pytest.raises(RiskInputError):
        risk_engine.assess(request)


def test_negative_required_prediction_is_rejected(
    risk_engine,
    low_risk_request,
) -> None:
    prediction = low_risk_request.predictions[-1]
    values = list(prediction.predictions)
    values[0] = values[0].model_copy(update={"value": -1.0})
    changed = prediction.model_copy(update={"predictions": tuple(values)})
    request = low_risk_request.model_copy(
        update={"predictions": (*low_risk_request.predictions[:-1], changed)}
    )

    with pytest.raises(RiskInputError):
        risk_engine.assess(request)


def test_missing_required_player_baseline_is_rejected(
    risk_engine,
    low_risk_request,
) -> None:
    baseline = low_risk_request.baseline.model_copy(
        update={"target_values": low_risk_request.baseline.target_values[:-1]}
    )
    request = low_risk_request.model_copy(update={"baseline": baseline})

    with pytest.raises(RiskInputError):
        risk_engine.assess(request)
