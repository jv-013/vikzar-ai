"""Transparent deterministic recommendations for qualified human review."""

from __future__ import annotations

from .contracts import (
    AsymmetryIndicator,
    AsymmetryStatus,
    FatigueIndicator,
    FatigueLevel,
    MuscleBalanceIndicator,
    MuscleBalanceStatus,
    RecommendationPriority,
    RiskLevel,
    RiskRecommendation,
    WorkloadIndicator,
    WorkloadStatus,
)

_PRIORITY_ORDER = {
    RecommendationPriority.IMMEDIATE: 0,
    RecommendationPriority.SOON: 1,
    RecommendationPriority.ROUTINE: 2,
}


class RecommendationEngine:
    """Map named rule outcomes to non-autonomous human-review guidance."""

    def generate(
        self,
        *,
        risk_level: RiskLevel,
        asymmetry: AsymmetryIndicator,
        fatigue: FatigueIndicator,
        workload: WorkloadIndicator,
        muscle_balance: MuscleBalanceIndicator,
    ) -> tuple[RiskRecommendation, ...]:
        recommendations: dict[str, RiskRecommendation] = {}
        if risk_level is RiskLevel.CRITICAL:
            recommendations["CLINICAL_REVIEW"] = RiskRecommendation(
                code="CLINICAL_REVIEW",
                priority=RecommendationPriority.IMMEDIATE,
                message=(
                    "Pause high-intensity participation pending review by a "
                    "qualified sports-medicine professional."
                ),
                rationale="The configured combined risk indicator is critical.",
            )
        elif risk_level is RiskLevel.HIGH:
            recommendations["LOAD_MODIFICATION_REVIEW"] = RiskRecommendation(
                code="LOAD_MODIFICATION_REVIEW",
                priority=RecommendationPriority.SOON,
                message=(
                    "Have qualified staff review session intensity and the "
                    "contributing indicators before further high-intensity work."
                ),
                rationale="The configured combined risk indicator is high.",
            )
        if asymmetry.status is not AsymmetryStatus.BALANCED:
            recommendations["BILATERAL_TECHNIQUE_REVIEW"] = RiskRecommendation(
                code="BILATERAL_TECHNIQUE_REVIEW",
                priority=(
                    RecommendationPriority.SOON
                    if asymmetry.status
                    in {AsymmetryStatus.HIGH, AsymmetryStatus.CRITICAL}
                    else RecommendationPriority.ROUTINE
                ),
                message=(
                    "Review bilateral mechanics and repeat a controlled "
                    "comparison under consistent conditions."
                ),
                rationale="Configured inter-limb asymmetry exceeded its watch band.",
            )
        if fatigue.level is not FatigueLevel.LOW:
            recommendations["RECOVERY_REVIEW"] = RiskRecommendation(
                code="RECOVERY_REVIEW",
                priority=(
                    RecommendationPriority.SOON
                    if fatigue.level in {FatigueLevel.HIGH, FatigueLevel.SEVERE}
                    else RecommendationPriority.ROUTINE
                ),
                message=(
                    "Review recovery status, exertion context, and fatigue "
                    "evidence before increasing training demand."
                ),
                rationale="The configured fatigue indicator is elevated.",
            )
        if workload.status in {
            WorkloadStatus.ELEVATED,
            WorkloadStatus.EXCESSIVE,
        }:
            recommendations["WORKLOAD_REVIEW"] = RiskRecommendation(
                code="WORKLOAD_REVIEW",
                priority=(
                    RecommendationPriority.IMMEDIATE
                    if workload.status is WorkloadStatus.EXCESSIVE
                    else RecommendationPriority.SOON
                ),
                message=(
                    "Review current session exposure against the player's "
                    "approved workload baseline."
                ),
                rationale="Intensity-weighted session exposure is elevated.",
            )
        if muscle_balance.status is not MuscleBalanceStatus.WITHIN_RANGE:
            recommendations["MUSCLE_BALANCE_REVIEW"] = RiskRecommendation(
                code="MUSCLE_BALANCE_REVIEW",
                priority=(
                    RecommendationPriority.SOON
                    if muscle_balance.status
                    in {
                        MuscleBalanceStatus.HIGH,
                        MuscleBalanceStatus.CRITICAL,
                    }
                    else RecommendationPriority.ROUTINE
                ),
                message=(
                    "Have qualified staff review the configured muscle-balance "
                    "indicator alongside other clinical evidence."
                ),
                rationale="The configured target-ratio range was exceeded.",
            )
        if not recommendations:
            recommendations["CONTINUE_MONITORING"] = RiskRecommendation(
                code="CONTINUE_MONITORING",
                priority=RecommendationPriority.ROUTINE,
                message="Continue the planned monitoring protocol.",
                rationale="No configured indicator exceeded its watch category.",
            )
        return tuple(
            sorted(
                recommendations.values(),
                key=lambda item: (_PRIORITY_ORDER[item.priority], item.code),
            )
        )
