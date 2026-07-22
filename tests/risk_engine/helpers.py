"""Phase 8 prediction and explicit clinical-policy fixtures for Phase 9."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.inference import InferenceMetadata, InferencePrediction, PredictionValue
from app.risk_engine import (
    AsymmetryPolicy,
    BaselineTargetValue,
    ConfidenceWeights,
    FatiguePolicy,
    FatigueWeights,
    IntensityMultiplier,
    MuscleBalancePolicy,
    PlayerRiskBaseline,
    PlayerRiskContext,
    RatioBands,
    RiskAssessmentRequest,
    RiskEngineConfig,
    RiskWeights,
    ScoreBands,
    SessionRiskContext,
    WorkloadPolicy,
)

LEFT_GROUP = "left_lower_limb"
RIGHT_GROUP = "right_lower_limb"
QUADRICEPS = "target__quadriceps_rms"
HAMSTRING = "target__hamstring_rms"
TARGETS = (QUADRICEPS, HAMSTRING)
BASE_TIME = datetime(2026, 7, 19, 14, tzinfo=timezone.utc)


def make_config() -> RiskEngineConfig:
    """Return one explicit test policy; no business logic depends on its values."""

    return RiskEngineConfig(
        policy_id="acl-clinical-policy-test",
        policy_version="1.0.0-test",
        left_group_id=LEFT_GROUP,
        right_group_id=RIGHT_GROUP,
        quadriceps_target_name=QUADRICEPS,
        hamstring_target_name=HAMSTRING,
        asymmetry_target_names=tuple(sorted(TARGETS)),
        fatigue_target_names=tuple(sorted(TARGETS)),
        asymmetry_policy=AsymmetryPolicy(
            ratio_bands=RatioBands(watch=0.10, high=0.20, critical=0.30)
        ),
        muscle_balance_policy=MuscleBalancePolicy(
            lower_ratio=0.50,
            upper_ratio=0.80,
            critical_deviation=0.40,
            score_bands=ScoreBands(watch=25, high=50, critical=75),
        ),
        fatigue_policy=FatiguePolicy(
            baseline_deviation_full_scale=0.50,
            temporal_trend_full_scale=0.40,
            minimum_history_windows=2,
            weights=FatigueWeights(
                baseline_deviation=0.50,
                temporal_trend=0.30,
                reported_fatigue=0.20,
            ),
            score_bands=ScoreBands(watch=30, high=60, critical=80),
        ),
        workload_policy=WorkloadPolicy(
            window_time_scale_seconds=0.001,
            optimal_min_ratio=0.50,
            elevated_ratio=1.20,
            excessive_ratio=1.50,
            intensity_multipliers=(
                IntensityMultiplier(name="high", multiplier=1.50),
                IntensityMultiplier(name="low", multiplier=0.75),
                IntensityMultiplier(name="moderate", multiplier=1.00),
            ),
            default_intensity_multiplier=1.00,
        ),
        risk_weights=RiskWeights(
            asymmetry=0.25,
            fatigue=0.25,
            workload=0.20,
            muscle_balance=0.20,
            prior_injury=0.10,
        ),
        risk_score_bands=ScoreBands(watch=30, high=60, critical=80),
        confidence_weights=ConfidenceWeights(
            baseline_reliability=0.50,
            history_depth=0.30,
            metadata_completeness=0.20,
        ),
    )


def make_baseline(
    *,
    typical_session_load: float = 10.0,
    prior_acl_injury: bool = False,
    reliability: float = 0.90,
) -> PlayerRiskBaseline:
    values = tuple(
        sorted(
            (
                BaselineTargetValue(
                    group_id=group_id,
                    target_name=target_name,
                    value=(
                        50.0 if target_name == QUADRICEPS else 30.0
                    ),
                )
                for group_id in (LEFT_GROUP, RIGHT_GROUP)
                for target_name in TARGETS
            ),
            key=lambda value: (value.group_id, value.target_name),
        )
    )
    return PlayerRiskBaseline(
        baseline_id="baseline-player-001",
        baseline_version="1.0.0",
        player_id="player-001",
        target_values=values,
        typical_session_load=typical_session_load,
        reliability=reliability,
        sample_count=20,
        prior_acl_injury=prior_acl_injury,
    )


def make_prediction(
    *,
    group_id: str,
    source_id: str,
    timestamp_offset_seconds: int,
    window_start: float,
    window_end: float,
    quadriceps: float,
    hamstring: float,
    model_id: str = "production-model-001",
) -> InferencePrediction:
    metadata = InferenceMetadata(
        model_id=model_id,
        model_version="1.0.0",
        model_checksum="a" * 64,
        model_configuration_hash="b" * 64,
        registration_id="production-registration-001",
        selection_id="production-selection-001",
        inference_configuration_hash="c" * 64,
        source_feature_vector_id=source_id,
        source_schema_version="1.0.0",
        source_timestamp=BASE_TIME + timedelta(seconds=timestamp_offset_seconds),
        player_id="player-001",
        session_id="session-001",
        group_id=group_id,
        window_start=window_start,
        window_end=window_end,
        feature_schema=(
            "feature__motion__mean_angular_velocity",
            "feature__motion__peak_resultant_acceleration",
        ),
        target_schema=TARGETS,
    )
    return InferencePrediction.create(
        predictions=(
            PredictionValue(target_name=QUADRICEPS, value=quadriceps),
            PredictionValue(target_name=HAMSTRING, value=hamstring),
        ),
        metadata=metadata,
    )


def make_request(
    *,
    high_risk: bool = False,
    reverse_predictions: bool = False,
) -> RiskAssessmentRequest:
    first = (
        make_prediction(
            group_id=LEFT_GROUP,
            source_id="feature-window-001",
            timestamp_offset_seconds=0,
            window_start=0,
            window_end=1000,
            quadriceps=50,
            hamstring=30,
        ),
        make_prediction(
            group_id=RIGHT_GROUP,
            source_id="feature-window-001",
            timestamp_offset_seconds=0,
            window_start=0,
            window_end=1000,
            quadriceps=50,
            hamstring=30,
        ),
    )
    latest_values = (
        (100.0, 10.0, 40.0, 50.0)
        if high_risk
        else (52.0, 31.0, 51.0, 30.5)
    )
    second = (
        make_prediction(
            group_id=LEFT_GROUP,
            source_id="feature-window-002",
            timestamp_offset_seconds=1,
            window_start=1000,
            window_end=2000,
            quadriceps=latest_values[0],
            hamstring=latest_values[1],
        ),
        make_prediction(
            group_id=RIGHT_GROUP,
            source_id="feature-window-002",
            timestamp_offset_seconds=1,
            window_start=1000,
            window_end=2000,
            quadriceps=latest_values[2],
            hamstring=latest_values[3],
        ),
    )
    predictions = first + second
    if reverse_predictions:
        predictions = tuple(reversed(predictions))
    return RiskAssessmentRequest(
        predictions=predictions,
        player=PlayerRiskContext(
            player_id="player-001",
            age=24,
            sex="male",
            dominant_leg="right",
            position="midfielder",
        ),
        session=SessionRiskContext(
            session_id="session-001",
            drill="cutting",
            training_intensity="high" if high_risk else "moderate",
            reported_fatigue=90.0 if high_risk else 20.0,
        ),
        baseline=make_baseline(
            typical_session_load=2.0 if high_risk else 10.0,
            prior_acl_injury=high_risk,
        ),
    )
