"""Deterministic non-diagnostic fatigue indicator from allowed evidence."""

from __future__ import annotations

from .configuration import RiskEngineConfig
from .contracts import FatigueIndicator
from .rule_engine import clamp_score, fatigue_level
from .validation import ValidatedRiskContext


class FatigueAnalyzer:
    """Combine individual-baseline deviation, temporal trend, and self-report."""

    def analyze(
        self,
        context: ValidatedRiskContext,
        config: RiskEngineConfig,
    ) -> FatigueIndicator:
        policy = config.fatigue_policy
        deviations: list[float] = []
        trends: list[float] = []
        for group_id in (config.left_group_id, config.right_group_id):
            latest = context.latest_by_group[group_id]
            latest_values = context.values_by_prediction[latest.prediction_id]
            for target_name in config.fatigue_target_names:
                baseline = context.baseline_values[(group_id, target_name)]
                deviations.append(
                    max(0.0, (latest_values[target_name] - baseline) / baseline)
                )
                history = tuple(
                    context.values_by_prediction[prediction.prediction_id][
                        target_name
                    ]
                    for prediction in context.predictions
                    if prediction.metadata.group_id == group_id
                )
                if len(history) >= policy.minimum_history_windows:
                    trends.append(max(0.0, (history[-1] - history[0]) / baseline))

        baseline_deviation = sum(deviations) / len(deviations)
        temporal_trend = (
            sum(trends) / len(trends) if trends else None
        )
        evidence: list[tuple[float, float]] = [
            (
                policy.weights.baseline_deviation,
                min(
                    1.0,
                    baseline_deviation / policy.baseline_deviation_full_scale,
                ),
            )
        ]
        if temporal_trend is not None:
            evidence.append(
                (
                    policy.weights.temporal_trend,
                    min(1.0, temporal_trend / policy.temporal_trend_full_scale),
                )
            )
        reported = context.request.session.reported_fatigue
        if reported is not None:
            evidence.append(
                (policy.weights.reported_fatigue, reported / 100.0)
            )
        available_weight = sum(weight for weight, _ in evidence)
        score = clamp_score(
            100.0
            * sum(weight * value for weight, value in evidence)
            / available_weight
        )
        return FatigueIndicator(
            score=score,
            level=fatigue_level(score, policy.score_bands),
            baseline_deviation=baseline_deviation,
            temporal_trend=temporal_trend,
            reported_fatigue=reported,
            history_windows=context.history_windows,
        )
