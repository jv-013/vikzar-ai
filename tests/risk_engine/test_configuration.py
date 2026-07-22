"""Version, immutability, and threshold validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.risk_engine import FatigueWeights, RiskWeights, ScoreBands
from tests.risk_engine.helpers import make_config


def test_configuration_is_immutable_versioned_and_deterministic() -> None:
    first = make_config()
    second = make_config()

    assert first.schema_version == "1.0.0"
    assert first.configuration_hash == second.configuration_hash
    with pytest.raises(ValidationError):
        first.policy_version = "changed"  # type: ignore[misc]


def test_risk_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        RiskWeights(
            asymmetry=0.25,
            fatigue=0.25,
            workload=0.25,
            muscle_balance=0.25,
            prior_injury=0.25,
        )


def test_threshold_bands_must_be_strictly_ordered() -> None:
    with pytest.raises(ValidationError):
        ScoreBands(watch=50, high=40, critical=80)


def test_fatigue_requires_always_available_baseline_evidence() -> None:
    config = make_config()
    with pytest.raises(ValidationError):
        config.fatigue_policy.model_copy(
            update={
                "weights": FatigueWeights(
                    baseline_deviation=0,
                    temporal_trend=0,
                    reported_fatigue=1,
                )
            }
        ).model_validate(
            {
                **config.fatigue_policy.model_dump(),
                "weights": {
                    "baseline_deviation": 0,
                    "temporal_trend": 0,
                    "reported_fatigue": 1,
                },
            }
        )


def test_configuration_rejects_non_finite_policy_values() -> None:
    payload = make_config().model_dump(mode="python")
    payload["workload_policy"]["window_time_scale_seconds"] = float("inf")

    with pytest.raises(ValidationError):
        type(make_config()).model_validate(payload)
