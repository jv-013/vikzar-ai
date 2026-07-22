"""End-to-end risk score, provenance, and deterministic-output tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.risk_engine import RiskLevel
from tests.risk_engine.helpers import make_request


def test_low_risk_assessment_is_complete_and_explainable(
    risk_engine,
    low_risk_request,
) -> None:
    assessment = risk_engine.assess(low_risk_request)

    assert assessment.risk_level is RiskLevel.LOW
    assert 0 <= assessment.risk_score < 30
    assert len(assessment.contributing_factors) == 5
    assert sum(
        factor.weighted_contribution
        for factor in assessment.contributing_factors
    ) == pytest.approx(assessment.risk_score)
    assert assessment.provenance.prediction_ids
    assert assessment.provenance.configuration_hash == (
        risk_engine.configuration_hash
    )
    assert assessment.recommendations[0].code == "CONTINUE_MONITORING"


def test_high_risk_assessment_generates_alerts_and_recommendations(
    risk_engine,
    high_risk_request,
) -> None:
    assessment = risk_engine.assess(high_risk_request)
    alert_codes = {alert.code for alert in assessment.alerts}
    recommendation_codes = {
        recommendation.code for recommendation in assessment.recommendations
    }

    assert assessment.risk_level is RiskLevel.CRITICAL
    assert assessment.risk_score > 80
    assert "ACL_RISK_CRITICAL" in alert_codes
    assert "ASYMMETRY_CRITICAL" in alert_codes
    assert "FATIGUE_SEVERE" in alert_codes
    assert "WORKLOAD_EXCESSIVE" in alert_codes
    assert "CLINICAL_REVIEW" in recommendation_codes
    assert "WORKLOAD_REVIEW" in recommendation_codes


def test_identical_inputs_and_configuration_are_byte_reproducible(
    risk_engine,
    low_risk_request,
) -> None:
    first = risk_engine.assess(low_risk_request)
    second = risk_engine.assess(low_risk_request)

    assert first.model_dump_json() == second.model_dump_json()
    assert first.assessment_id == second.assessment_id
    assert first.checksum == second.checksum


def test_prediction_input_order_does_not_change_assessment(risk_engine) -> None:
    ordered = risk_engine.assess(make_request())
    reversed_input = risk_engine.assess(
        make_request(reverse_predictions=True)
    )

    assert ordered == reversed_input


def test_assessment_contract_is_immutable_and_checksum_bound(
    risk_engine,
    low_risk_request,
) -> None:
    assessment = risk_engine.assess(low_risk_request)
    with pytest.raises(ValidationError):
        assessment.risk_score = 100  # type: ignore[misc]

    payload = assessment.model_dump(mode="json")
    payload["risk_score"] = 100
    with pytest.raises(ValidationError):
        type(assessment).model_validate(payload)
