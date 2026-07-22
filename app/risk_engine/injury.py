"""Explainable weighted ACL risk scoring over transparent indicators."""

from __future__ import annotations

from .configuration import RiskEngineConfig
from .contracts import (
    AsymmetryIndicator,
    ContributingFactor,
    FatigueIndicator,
    MuscleBalanceIndicator,
    RiskComponent,
    WorkloadIndicator,
)
from .rule_engine import clamp_score
from .validation import ValidatedRiskContext


class ACLRiskScorer:
    """Combine configured components without inference or hidden rules."""

    def score(
        self,
        *,
        context: ValidatedRiskContext,
        asymmetry: AsymmetryIndicator,
        fatigue: FatigueIndicator,
        workload: WorkloadIndicator,
        muscle_balance: MuscleBalanceIndicator,
        config: RiskEngineConfig,
    ) -> tuple[float, tuple[ContributingFactor, ...]]:
        prior_injury_score = (
            100.0 if context.request.baseline.prior_acl_injury else 0.0
        )
        values = {
            RiskComponent.ASYMMETRY: (
                asymmetry.score,
                config.risk_weights.asymmetry,
                "Mean configured bilateral percent-difference indicator.",
            ),
            RiskComponent.FATIGUE: (
                fatigue.score,
                config.risk_weights.fatigue,
                "Configured baseline, temporal, and available self-report evidence.",
            ),
            RiskComponent.WORKLOAD: (
                workload.score,
                config.risk_weights.workload,
                "Current intensity-weighted exposure relative to the player baseline.",
            ),
            RiskComponent.MUSCLE_BALANCE: (
                muscle_balance.score,
                config.risk_weights.muscle_balance,
                "Configured hamstring-to-quadriceps target-ratio deviation.",
            ),
            RiskComponent.PRIOR_INJURY: (
                prior_injury_score,
                config.risk_weights.prior_injury,
                "Explicit prior ACL history from the versioned player baseline.",
            ),
        }
        factors = tuple(
            ContributingFactor(
                component=component,
                component_score=values[component][0],
                weight=values[component][1],
                weighted_contribution=(
                    values[component][0] * values[component][1]
                ),
                rationale=values[component][2],
            )
            for component in RiskComponent
        )
        return (
            clamp_score(
                sum(factor.weighted_contribution for factor in factors)
            ),
            factors,
        )
