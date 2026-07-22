"""Immutable Phase 9 inputs, indicators, explanations, and output contracts."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import risk_engine_config
from app.inference.contracts import InferencePrediction
from app.schemas.player import Player
from app.schemas.session import Session


class RiskLevel(str, Enum):
    """Configured overall ACL risk category."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class FatigueLevel(str, Enum):
    """Non-diagnostic fatigue-indicator category."""

    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"
    SEVERE = "severe"


class WorkloadStatus(str, Enum):
    """Individual-baseline session exposure status."""

    UNDER_BASELINE = "under_baseline"
    WITHIN_BASELINE = "within_baseline"
    ELEVATED = "elevated"
    EXCESSIVE = "excessive"


class AsymmetryStatus(str, Enum):
    """Configured inter-limb asymmetry category."""

    BALANCED = "balanced"
    WATCH = "watch"
    HIGH = "high"
    CRITICAL = "critical"


class MuscleBalanceStatus(str, Enum):
    """Configured hamstring-to-quadriceps balance category."""

    WITHIN_RANGE = "within_range"
    WATCH = "watch"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSeverity(str, Enum):
    """Operational alert severity, ordered by rule-engine policy."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationPriority(str, Enum):
    """Operational urgency for a transparent recommendation."""

    ROUTINE = "routine"
    SOON = "soon"
    IMMEDIATE = "immediate"


class RiskComponent(str, Enum):
    """Named explainable components of the overall risk score."""

    ASYMMETRY = "asymmetry"
    FATIGUE = "fatigue"
    WORKLOAD = "workload"
    MUSCLE_BALANCE = "muscle_balance"
    PRIOR_INJURY = "prior_injury"


class PlayerRiskContext(BaseModel):
    """Immutable snapshot of allowed player metadata."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    player_id: str = Field(min_length=1)
    age: int = Field(ge=0)
    sex: str = Field(min_length=1)
    dominant_leg: str = Field(min_length=1)
    position: str = Field(min_length=1)
    injury_history: str | None = None
    injury_status: str | None = None

    @classmethod
    def from_player(cls, player: Player) -> "PlayerRiskContext":
        """Snapshot the existing runtime Player contract without mutating it."""

        return cls(
            player_id=player.player_id,
            age=player.age,
            sex=player.sex,
            dominant_leg=player.dominant_leg,
            position=player.position,
            injury_history=player.injury_history,
            injury_status=player.injury_status,
        )


class SessionRiskContext(BaseModel):
    """Immutable snapshot of session metadata permitted at the Phase 9 boundary."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    session_id: str = Field(min_length=1)
    drill: str | None = None
    training_intensity: str | None = None
    reported_fatigue: float | None = Field(default=None, ge=0, le=100)

    @classmethod
    def from_session(cls, session: Session) -> "SessionRiskContext":
        """Snapshot the existing runtime Session contract without mutating it."""

        return cls(
            session_id=session.session_id,
            drill=session.drill,
            training_intensity=session.training_intensity,
            reported_fatigue=session.fatigue_level,
        )


class BaselineTargetValue(BaseModel):
    """One positive individual reference value for a group and model target."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    group_id: str = Field(min_length=1)
    target_name: str = Field(min_length=1)
    value: float = Field(gt=0)

    @field_validator("value")
    @classmethod
    def validate_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Baseline target values must be finite.")
        return value


class PlayerRiskBaseline(BaseModel):
    """Versioned player baseline supplied by an approved offline process."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    baseline_id: str = Field(min_length=1)
    baseline_version: str = Field(min_length=1)
    player_id: str = Field(min_length=1)
    target_values: tuple[BaselineTargetValue, ...] = Field(min_length=1)
    typical_session_load: float = Field(gt=0)
    reliability: float = Field(ge=0, le=1)
    sample_count: int = Field(ge=1)
    prior_acl_injury: bool

    @field_validator("typical_session_load")
    @classmethod
    def validate_finite_load(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Typical session load must be finite.")
        return value

    @field_validator("target_values")
    @classmethod
    def validate_targets(
        cls,
        values: tuple[BaselineTargetValue, ...],
    ) -> tuple[BaselineTargetValue, ...]:
        keys = tuple((value.group_id, value.target_name) for value in values)
        if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
            raise ValueError(
                "Baseline target values must be unique and deterministically ordered."
            )
        return values


class RiskAssessmentRequest(BaseModel):
    """Only Phase 8 predictions and immutable allowed metadata enter Phase 9."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    predictions: tuple[InferencePrediction, ...] = Field(min_length=2)
    player: PlayerRiskContext
    session: SessionRiskContext
    baseline: PlayerRiskBaseline

    @classmethod
    def from_runtime(
        cls,
        *,
        predictions: tuple[InferencePrediction, ...],
        player: Player,
        session: Session,
        baseline: PlayerRiskBaseline,
    ) -> "RiskAssessmentRequest":
        """Create an immutable request from existing runtime metadata contracts."""

        return cls(
            predictions=predictions,
            player=PlayerRiskContext.from_player(player),
            session=SessionRiskContext.from_session(session),
            baseline=baseline,
        )


class AsymmetryTargetIndicator(BaseModel):
    """Explain one bilateral percent-difference calculation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    target_name: str = Field(min_length=1)
    left_value: float
    right_value: float
    asymmetry_ratio: float = Field(ge=0)
    score: float = Field(ge=0, le=100)


class AsymmetryIndicator(BaseModel):
    """Aggregate configured bilateral prediction differences."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    score: float = Field(ge=0, le=100)
    status: AsymmetryStatus
    targets: tuple[AsymmetryTargetIndicator, ...] = Field(min_length=1)


class FatigueIndicator(BaseModel):
    """Transparent, non-diagnostic baseline/trend/self-report indicator."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    score: float = Field(ge=0, le=100)
    level: FatigueLevel
    baseline_deviation: float = Field(ge=0)
    temporal_trend: float | None = Field(default=None, ge=0)
    reported_fatigue: float | None = Field(default=None, ge=0, le=100)
    history_windows: int = Field(ge=1)


class WorkloadIndicator(BaseModel):
    """Individual-baseline intensity-weighted session exposure."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    score: float = Field(ge=0, le=100)
    status: WorkloadStatus
    exposure_seconds: float = Field(ge=0)
    intensity_multiplier: float = Field(gt=0)
    current_load: float = Field(ge=0)
    baseline_load: float = Field(gt=0)
    workload_ratio: float = Field(ge=0)


class MuscleBalanceSideIndicator(BaseModel):
    """Configured hamstring-to-quadriceps ratio for one limb group."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    group_id: str = Field(min_length=1)
    ratio: float = Field(ge=0)
    score: float = Field(ge=0, le=100)


class MuscleBalanceIndicator(BaseModel):
    """Aggregate configured target-ratio balance indicator."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    score: float = Field(ge=0, le=100)
    status: MuscleBalanceStatus
    sides: tuple[MuscleBalanceSideIndicator, ...] = Field(min_length=2)


class TriggeredAlert(BaseModel):
    """One deterministic operational alert with no autonomous external action."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    code: str = Field(min_length=1)
    severity: AlertSeverity
    message: str = Field(min_length=1)
    component: RiskComponent | None = None


class ContributingFactor(BaseModel):
    """One exact weighted component retained for full score explanation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    component: RiskComponent
    component_score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    weighted_contribution: float = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)


class RiskRecommendation(BaseModel):
    """One deterministic human-review recommendation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    code: str = Field(min_length=1)
    priority: RecommendationPriority
    message: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class RiskProvenance(BaseModel):
    """Complete prediction and policy lineage for one assessment."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    schema_version: str = risk_engine_config.RISK_ENGINE_SCHEMA_VERSION
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    configuration_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    baseline_id: str = Field(min_length=1)
    baseline_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    model_checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    inference_configuration_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    player_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    assessed_at: datetime
    prediction_ids: tuple[str, ...] = Field(min_length=2)
    prediction_checksums: tuple[str, ...] = Field(min_length=2)


class RiskAssessment(BaseModel):
    """Versioned deterministic ACL risk indicator and explanation output."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    assessment_id: str = Field(min_length=1)
    schema_version: str = risk_engine_config.RISK_ENGINE_SCHEMA_VERSION
    risk_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    fatigue: FatigueIndicator
    workload: WorkloadIndicator
    asymmetry: AsymmetryIndicator
    muscle_balance: MuscleBalanceIndicator
    alerts: tuple[TriggeredAlert, ...]
    contributing_factors: tuple[ContributingFactor, ...] = Field(min_length=5)
    recommendations: tuple[RiskRecommendation, ...] = Field(min_length=1)
    provenance: RiskProvenance
    checksum: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> "RiskAssessment":
        if self.schema_version != risk_engine_config.RISK_ENGINE_SCHEMA_VERSION:
            raise ValueError("Unsupported RiskAssessment schema version.")
        components = tuple(
            factor.component for factor in self.contributing_factors
        )
        if components != tuple(RiskComponent):
            raise ValueError(
                "Risk factors must contain every component in deterministic order."
            )
        expected = self.calculate_checksum(
            risk_score=self.risk_score,
            risk_level=self.risk_level,
            confidence=self.confidence,
            fatigue=self.fatigue,
            workload=self.workload,
            asymmetry=self.asymmetry,
            muscle_balance=self.muscle_balance,
            alerts=self.alerts,
            contributing_factors=self.contributing_factors,
            recommendations=self.recommendations,
            provenance=self.provenance,
        )
        if self.checksum.lower() != expected:
            raise ValueError("Risk assessment checksum does not match its content.")
        if self.assessment_id != f"risk-assessment-{expected[:24]}":
            raise ValueError("Risk assessment ID does not match its content.")
        return self

    @classmethod
    def create(
        cls,
        *,
        risk_score: float,
        risk_level: RiskLevel,
        confidence: float,
        fatigue: FatigueIndicator,
        workload: WorkloadIndicator,
        asymmetry: AsymmetryIndicator,
        muscle_balance: MuscleBalanceIndicator,
        alerts: tuple[TriggeredAlert, ...],
        contributing_factors: tuple[ContributingFactor, ...],
        recommendations: tuple[RiskRecommendation, ...],
        provenance: RiskProvenance,
    ) -> "RiskAssessment":
        checksum = cls.calculate_checksum(
            risk_score=risk_score,
            risk_level=risk_level,
            confidence=confidence,
            fatigue=fatigue,
            workload=workload,
            asymmetry=asymmetry,
            muscle_balance=muscle_balance,
            alerts=alerts,
            contributing_factors=contributing_factors,
            recommendations=recommendations,
            provenance=provenance,
        )
        return cls(
            assessment_id=f"risk-assessment-{checksum[:24]}",
            risk_score=risk_score,
            risk_level=risk_level,
            confidence=confidence,
            fatigue=fatigue,
            workload=workload,
            asymmetry=asymmetry,
            muscle_balance=muscle_balance,
            alerts=alerts,
            contributing_factors=contributing_factors,
            recommendations=recommendations,
            provenance=provenance,
            checksum=checksum,
        )

    @staticmethod
    def calculate_checksum(**values: object) -> str:
        payload = {
            name: (
                value.model_dump(mode="json")
                if hasattr(value, "model_dump")
                else [
                    item.model_dump(mode="json") for item in value
                ]
                if isinstance(value, tuple)
                else value.value
                if isinstance(value, Enum)
                else value
            )
            for name, value in values.items()
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
