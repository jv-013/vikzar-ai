"""Public deterministic Phase 9 ACL Risk Engine."""

from __future__ import annotations

from pydantic import ValidationError

from .alerts import AlertGenerator
from .asymmetry import AsymmetryAnalyzer
from .configuration import RiskEngineConfig
from .contracts import (
    RiskAssessment,
    RiskAssessmentRequest,
    RiskProvenance,
)
from .exceptions import RiskComputationError, RiskOutputError
from .fatigue import FatigueAnalyzer
from .injury import ACLRiskScorer
from .muscle import MuscleBalanceAnalyzer
from .recommendations import RecommendationEngine
from .rule_engine import risk_level
from .validation import RiskInputValidator, ValidatedRiskContext
from .workload import WorkloadAnalyzer


class ACLRiskEngine:
    """Transform only validated Phase 8 outputs into an explainable assessment."""

    def __init__(
        self,
        config: RiskEngineConfig,
        *,
        validator: RiskInputValidator | None = None,
        asymmetry_analyzer: AsymmetryAnalyzer | None = None,
        fatigue_analyzer: FatigueAnalyzer | None = None,
        workload_analyzer: WorkloadAnalyzer | None = None,
        muscle_balance_analyzer: MuscleBalanceAnalyzer | None = None,
        scorer: ACLRiskScorer | None = None,
        alert_generator: AlertGenerator | None = None,
        recommendation_engine: RecommendationEngine | None = None,
    ) -> None:
        self._config = config
        self._validator = validator or RiskInputValidator()
        self._asymmetry = asymmetry_analyzer or AsymmetryAnalyzer()
        self._fatigue = fatigue_analyzer or FatigueAnalyzer()
        self._workload = workload_analyzer or WorkloadAnalyzer()
        self._muscle_balance = (
            muscle_balance_analyzer or MuscleBalanceAnalyzer()
        )
        self._scorer = scorer or ACLRiskScorer()
        self._alerts = alert_generator or AlertGenerator()
        self._recommendations = (
            recommendation_engine or RecommendationEngine()
        )

    @property
    def configuration_hash(self) -> str:
        """Return the exact immutable clinical policy identity."""

        return self._config.configuration_hash

    def assess(self, request: RiskAssessmentRequest) -> RiskAssessment:
        """Produce one deterministic, non-diagnostic ACL risk assessment."""

        context = self._validator.validate(request, self._config)
        try:
            asymmetry = self._asymmetry.analyze(context, self._config)
            fatigue = self._fatigue.analyze(context, self._config)
            workload = self._workload.analyze(context, self._config)
            muscle_balance = self._muscle_balance.analyze(context, self._config)
            score, factors = self._scorer.score(
                context=context,
                asymmetry=asymmetry,
                fatigue=fatigue,
                workload=workload,
                muscle_balance=muscle_balance,
                config=self._config,
            )
        except (ArithmeticError, ValidationError, ValueError) as exc:
            raise RiskComputationError(
                "Configured risk computation could not produce finite indicators."
            ) from exc
        level = risk_level(score, self._config.risk_score_bands)
        confidence = self._confidence(context)
        alerts = self._alerts.generate(
            context=context,
            risk_level=level,
            asymmetry=asymmetry,
            fatigue=fatigue,
            workload=workload,
            muscle_balance=muscle_balance,
        )
        recommendations = self._recommendations.generate(
            risk_level=level,
            asymmetry=asymmetry,
            fatigue=fatigue,
            workload=workload,
            muscle_balance=muscle_balance,
        )
        first = context.predictions[0].metadata
        provenance = RiskProvenance(
            policy_id=self._config.policy_id,
            policy_version=self._config.policy_version,
            configuration_hash=self._config.configuration_hash,
            baseline_id=request.baseline.baseline_id,
            baseline_version=request.baseline.baseline_version,
            model_id=first.model_id,
            model_version=first.model_version,
            model_checksum=first.model_checksum,
            inference_configuration_hash=first.inference_configuration_hash,
            player_id=request.player.player_id,
            session_id=request.session.session_id,
            assessed_at=max(
                prediction.metadata.source_timestamp
                for prediction in context.predictions
            ),
            prediction_ids=tuple(
                prediction.prediction_id for prediction in context.predictions
            ),
            prediction_checksums=tuple(
                prediction.checksum for prediction in context.predictions
            ),
        )
        try:
            return RiskAssessment.create(
                risk_score=score,
                risk_level=level,
                confidence=confidence,
                fatigue=fatigue,
                workload=workload,
                asymmetry=asymmetry,
                muscle_balance=muscle_balance,
                alerts=alerts,
                contributing_factors=factors,
                recommendations=recommendations,
                provenance=provenance,
            )
        except (ValidationError, ValueError) as exc:
            raise RiskOutputError(
                "Risk Engine produced an invalid assessment contract."
            ) from exc

    def _confidence(self, context: ValidatedRiskContext) -> float:
        """Quantify evidence completeness without claiming model confidence."""

        weights = self._config.confidence_weights
        history_depth = min(
            1.0,
            context.history_windows
            / self._config.fatigue_policy.minimum_history_windows,
        )
        return (
            weights.baseline_reliability
            * context.request.baseline.reliability
            + weights.history_depth * history_depth
            + weights.metadata_completeness
        )


RiskEngine = ACLRiskEngine
