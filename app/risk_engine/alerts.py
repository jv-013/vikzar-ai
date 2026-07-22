"""Deterministic alert generation without external side effects."""

from __future__ import annotations

from .contracts import (
    AlertSeverity,
    AsymmetryIndicator,
    AsymmetryStatus,
    FatigueIndicator,
    FatigueLevel,
    MuscleBalanceIndicator,
    MuscleBalanceStatus,
    RiskComponent,
    RiskLevel,
    TriggeredAlert,
    WorkloadIndicator,
    WorkloadStatus,
)
from .validation import ValidatedRiskContext

_SEVERITY_ORDER = {
    AlertSeverity.CRITICAL: 0,
    AlertSeverity.HIGH: 1,
    AlertSeverity.WARNING: 2,
    AlertSeverity.INFO: 3,
}


class AlertGenerator:
    """Generate stable alerts only from named output categories."""

    def generate(
        self,
        *,
        context: ValidatedRiskContext,
        risk_level: RiskLevel,
        asymmetry: AsymmetryIndicator,
        fatigue: FatigueIndicator,
        workload: WorkloadIndicator,
        muscle_balance: MuscleBalanceIndicator,
    ) -> tuple[TriggeredAlert, ...]:
        alerts: list[TriggeredAlert] = []
        if risk_level is RiskLevel.CRITICAL:
            alerts.append(
                TriggeredAlert(
                    code="ACL_RISK_CRITICAL",
                    severity=AlertSeverity.CRITICAL,
                    message="Configured combined ACL risk indicator is critical.",
                )
            )
        elif risk_level is RiskLevel.HIGH:
            alerts.append(
                TriggeredAlert(
                    code="ACL_RISK_HIGH",
                    severity=AlertSeverity.HIGH,
                    message="Configured combined ACL risk indicator is high.",
                )
            )
        self._component_alerts(
            alerts,
            asymmetry,
            fatigue,
            workload,
            muscle_balance,
        )
        if context.request.baseline.prior_acl_injury:
            alerts.append(
                TriggeredAlert(
                    code="PRIOR_ACL_HISTORY",
                    severity=AlertSeverity.INFO,
                    message="Versioned player baseline records prior ACL injury.",
                    component=RiskComponent.PRIOR_INJURY,
                )
            )
        return tuple(
            sorted(
                alerts,
                key=lambda item: (_SEVERITY_ORDER[item.severity], item.code),
            )
        )

    @staticmethod
    def _component_alerts(
        alerts: list[TriggeredAlert],
        asymmetry: AsymmetryIndicator,
        fatigue: FatigueIndicator,
        workload: WorkloadIndicator,
        muscle_balance: MuscleBalanceIndicator,
    ) -> None:
        if asymmetry.status in {
            AsymmetryStatus.HIGH,
            AsymmetryStatus.CRITICAL,
        }:
            alerts.append(
                TriggeredAlert(
                    code=f"ASYMMETRY_{asymmetry.status.value.upper()}",
                    severity=(
                        AlertSeverity.CRITICAL
                        if asymmetry.status is AsymmetryStatus.CRITICAL
                        else AlertSeverity.HIGH
                    ),
                    message="Configured bilateral prediction asymmetry is elevated.",
                    component=RiskComponent.ASYMMETRY,
                )
            )
        if fatigue.level in {FatigueLevel.HIGH, FatigueLevel.SEVERE}:
            alerts.append(
                TriggeredAlert(
                    code=f"FATIGUE_{fatigue.level.value.upper()}",
                    severity=(
                        AlertSeverity.CRITICAL
                        if fatigue.level is FatigueLevel.SEVERE
                        else AlertSeverity.HIGH
                    ),
                    message="Configured fatigue evidence indicator is elevated.",
                    component=RiskComponent.FATIGUE,
                )
            )
        if workload.status in {
            WorkloadStatus.ELEVATED,
            WorkloadStatus.EXCESSIVE,
        }:
            alerts.append(
                TriggeredAlert(
                    code=f"WORKLOAD_{workload.status.value.upper()}",
                    severity=(
                        AlertSeverity.CRITICAL
                        if workload.status is WorkloadStatus.EXCESSIVE
                        else AlertSeverity.WARNING
                    ),
                    message="Session exposure exceeds the configured player baseline range.",
                    component=RiskComponent.WORKLOAD,
                )
            )
        if muscle_balance.status in {
            MuscleBalanceStatus.HIGH,
            MuscleBalanceStatus.CRITICAL,
        }:
            alerts.append(
                TriggeredAlert(
                    code=f"MUSCLE_BALANCE_{muscle_balance.status.value.upper()}",
                    severity=(
                        AlertSeverity.CRITICAL
                        if muscle_balance.status
                        is MuscleBalanceStatus.CRITICAL
                        else AlertSeverity.HIGH
                    ),
                    message="Configured muscle target-ratio balance is outside range.",
                    component=RiskComponent.MUSCLE_BALANCE,
                )
            )
