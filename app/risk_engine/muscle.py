"""Configured hamstring-to-quadriceps prediction balance analysis."""

from __future__ import annotations

from .configuration import RiskEngineConfig
from .contracts import (
    MuscleBalanceIndicator,
    MuscleBalanceSideIndicator,
)
from .rule_engine import clamp_score, muscle_balance_status
from .validation import ValidatedRiskContext


class MuscleBalanceAnalyzer:
    """Calculate target ratios as one monitored factor, never a diagnosis."""

    def analyze(
        self,
        context: ValidatedRiskContext,
        config: RiskEngineConfig,
    ) -> MuscleBalanceIndicator:
        policy = config.muscle_balance_policy
        sides: list[MuscleBalanceSideIndicator] = []
        for group_id in (config.left_group_id, config.right_group_id):
            prediction = context.latest_by_group[group_id]
            values = context.values_by_prediction[prediction.prediction_id]
            quadriceps = values[config.quadriceps_target_name]
            hamstring = values[config.hamstring_target_name]
            if quadriceps == 0.0:
                ratio = (
                    0.0
                    if hamstring == 0.0
                    else policy.upper_ratio + policy.critical_deviation
                )
            else:
                ratio = hamstring / quadriceps
            if ratio < policy.lower_ratio:
                deviation = policy.lower_ratio - ratio
            elif ratio > policy.upper_ratio:
                deviation = ratio - policy.upper_ratio
            else:
                deviation = 0.0
            score = clamp_score(
                100.0 * deviation / policy.critical_deviation
            )
            sides.append(
                MuscleBalanceSideIndicator(
                    group_id=group_id,
                    ratio=ratio,
                    score=score,
                )
            )
        aggregate_score = max(side.score for side in sides)
        return MuscleBalanceIndicator(
            score=aggregate_score,
            status=muscle_balance_status(
                aggregate_score,
                policy.score_bands,
            ),
            sides=tuple(sides),
        )
