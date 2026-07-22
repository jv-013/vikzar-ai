"""Individual-baseline workload analysis from Phase 8 prediction metadata."""

from __future__ import annotations

from .configuration import RiskEngineConfig
from .contracts import WorkloadIndicator, WorkloadStatus
from .rule_engine import clamp_score
from .validation import ValidatedRiskContext


class WorkloadAnalyzer:
    """Calculate intensity-weighted union exposure without double-counting limbs."""

    def analyze(
        self,
        context: ValidatedRiskContext,
        config: RiskEngineConfig,
    ) -> WorkloadIndicator:
        policy = config.workload_policy
        intervals = sorted(
            {
                (
                    prediction.metadata.window_start,
                    prediction.metadata.window_end,
                )
                for prediction in context.predictions
            }
        )
        merged: list[list[float]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        exposure_seconds = (
            sum(end - start for start, end in merged)
            * policy.window_time_scale_seconds
        )
        intensity_name = (
            context.request.session.training_intensity or ""
        ).strip().lower()
        multipliers = {
            item.name: item.multiplier for item in policy.intensity_multipliers
        }
        multiplier = multipliers.get(
            intensity_name,
            policy.default_intensity_multiplier,
        )
        current_load = exposure_seconds * multiplier
        baseline_load = context.request.baseline.typical_session_load
        ratio = current_load / baseline_load
        if ratio >= policy.excessive_ratio:
            status = WorkloadStatus.EXCESSIVE
        elif ratio >= policy.elevated_ratio:
            status = WorkloadStatus.ELEVATED
        elif ratio < policy.optimal_min_ratio:
            status = WorkloadStatus.UNDER_BASELINE
        else:
            status = WorkloadStatus.WITHIN_BASELINE
        score = clamp_score(
            100.0
            * max(0.0, ratio - policy.elevated_ratio)
            / (policy.excessive_ratio - policy.elevated_ratio)
        )
        return WorkloadIndicator(
            score=score,
            status=status,
            exposure_seconds=exposure_seconds,
            intensity_multiplier=multiplier,
            current_load=current_load,
            baseline_load=baseline_load,
            workload_ratio=ratio,
        )
