"""Exact component-formula and status regression tests."""

from __future__ import annotations

import pytest

from app.risk_engine import (
    AsymmetryStatus,
    FatigueLevel,
    MuscleBalanceStatus,
    WorkloadStatus,
)


def test_asymmetry_uses_reference_limb_independent_percent_difference(
    risk_engine,
    high_risk_request,
) -> None:
    assessment = risk_engine.assess(high_risk_request)
    by_target = {
        target.target_name: target for target in assessment.asymmetry.targets
    }

    quadriceps = by_target["target__quadriceps_rms"]
    assert quadriceps.asymmetry_ratio == pytest.approx(60 / 70)
    assert assessment.asymmetry.status is AsymmetryStatus.CRITICAL


def test_workload_merges_duplicate_bilateral_windows(
    risk_engine,
    high_risk_request,
) -> None:
    workload = risk_engine.assess(high_risk_request).workload

    assert workload.exposure_seconds == pytest.approx(2.0)
    assert workload.current_load == pytest.approx(3.0)
    assert workload.workload_ratio == pytest.approx(1.5)
    assert workload.status is WorkloadStatus.EXCESSIVE


def test_fatigue_uses_baseline_trend_and_reported_evidence(
    risk_engine,
    high_risk_request,
) -> None:
    fatigue = risk_engine.assess(high_risk_request).fatigue

    assert fatigue.baseline_deviation > 0
    assert fatigue.temporal_trend is not None
    assert fatigue.reported_fatigue == 90
    assert fatigue.level is FatigueLevel.SEVERE


def test_muscle_balance_is_one_explicit_component_not_a_prediction(
    risk_engine,
    high_risk_request,
) -> None:
    balance = risk_engine.assess(high_risk_request).muscle_balance

    assert balance.status is MuscleBalanceStatus.CRITICAL
    assert {side.group_id for side in balance.sides} == {
        "left_lower_limb",
        "right_lower_limb",
    }
    assert max(side.score for side in balance.sides) == balance.score
