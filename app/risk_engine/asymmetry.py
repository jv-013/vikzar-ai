"""Transparent bilateral asymmetry analysis over Phase 8 predictions."""

from __future__ import annotations

from .configuration import RiskEngineConfig
from .contracts import AsymmetryIndicator, AsymmetryTargetIndicator
from .rule_engine import asymmetry_status, ratio_score
from .validation import ValidatedRiskContext


class AsymmetryAnalyzer:
    """Calculate reference-limb-independent percent differences."""

    def analyze(
        self,
        context: ValidatedRiskContext,
        config: RiskEngineConfig,
    ) -> AsymmetryIndicator:
        left = context.latest_by_group[config.left_group_id]
        right = context.latest_by_group[config.right_group_id]
        left_values = context.values_by_prediction[left.prediction_id]
        right_values = context.values_by_prediction[right.prediction_id]
        bands = config.asymmetry_policy.ratio_bands
        targets: list[AsymmetryTargetIndicator] = []
        for target_name in config.asymmetry_target_names:
            left_value = left_values[target_name]
            right_value = right_values[target_name]
            denominator = (abs(left_value) + abs(right_value)) / 2.0
            ratio = (
                0.0
                if denominator == 0.0
                else abs(left_value - right_value) / denominator
            )
            targets.append(
                AsymmetryTargetIndicator(
                    target_name=target_name,
                    left_value=left_value,
                    right_value=right_value,
                    asymmetry_ratio=ratio,
                    score=ratio_score(ratio, bands.critical),
                )
            )
        score = sum(target.score for target in targets) / len(targets)
        aggregate_ratio = sum(
            target.asymmetry_ratio for target in targets
        ) / len(targets)
        return AsymmetryIndicator(
            score=score,
            status=asymmetry_status(aggregate_ratio, bands),
            targets=tuple(targets),
        )
