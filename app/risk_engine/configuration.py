"""Immutable, versioned clinical policy configuration for Phase 9."""

from __future__ import annotations

import hashlib
import json
import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import risk_engine_config


class ScoreBands(BaseModel):
    """Ordered 0–100 boundaries used to name an indicator or risk score."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    watch: float = Field(ge=0, le=100)
    high: float = Field(ge=0, le=100)
    critical: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_order(self) -> "ScoreBands":
        if not self.watch < self.high < self.critical:
            raise ValueError("Score bands must be strictly increasing.")
        return self


class RatioBands(BaseModel):
    """Ordered positive ratio boundaries for asymmetry or workload status."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    watch: float = Field(ge=0)
    high: float = Field(gt=0)
    critical: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> "RatioBands":
        if not self.watch < self.high < self.critical:
            raise ValueError("Ratio bands must be strictly increasing.")
        return self


class RiskWeights(BaseModel):
    """Relative contribution of each transparent risk component."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    asymmetry: float = Field(ge=0, le=1)
    fatigue: float = Field(ge=0, le=1)
    workload: float = Field(ge=0, le=1)
    muscle_balance: float = Field(ge=0, le=1)
    prior_injury: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> "RiskWeights":
        if not math.isclose(
            self.asymmetry
            + self.fatigue
            + self.workload
            + self.muscle_balance
            + self.prior_injury,
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("Risk component weights must sum to 1.0.")
        return self


class FatigueWeights(BaseModel):
    """Evidence weights used for the non-diagnostic fatigue indicator."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    baseline_deviation: float = Field(ge=0, le=1)
    temporal_trend: float = Field(ge=0, le=1)
    reported_fatigue: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> "FatigueWeights":
        if not math.isclose(
            self.baseline_deviation
            + self.temporal_trend
            + self.reported_fatigue,
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("Fatigue evidence weights must sum to 1.0.")
        return self


class ConfidenceWeights(BaseModel):
    """Weights for evidence-confidence, not model uncertainty."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    baseline_reliability: float = Field(ge=0, le=1)
    history_depth: float = Field(ge=0, le=1)
    metadata_completeness: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> "ConfidenceWeights":
        if not math.isclose(
            self.baseline_reliability
            + self.history_depth
            + self.metadata_completeness,
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("Confidence evidence weights must sum to 1.0.")
        return self


class IntensityMultiplier(BaseModel):
    """One session-intensity vocabulary entry and exposure multiplier."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1)
    multiplier: float = Field(gt=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Intensity name must not be blank.")
        return normalized


class AsymmetryPolicy(BaseModel):
    """Configured inter-limb asymmetry interpretation policy."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    ratio_bands: RatioBands


class MuscleBalancePolicy(BaseModel):
    """Configured target-ratio range and full-scale deviation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    lower_ratio: float = Field(gt=0)
    upper_ratio: float = Field(gt=0)
    critical_deviation: float = Field(gt=0)
    score_bands: ScoreBands

    @model_validator(mode="after")
    def validate_range(self) -> "MuscleBalancePolicy":
        if self.lower_ratio >= self.upper_ratio:
            raise ValueError("Muscle-balance lower ratio must be below upper ratio.")
        return self


class FatiguePolicy(BaseModel):
    """Configured baseline, trend, self-report, and severity interpretation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    baseline_deviation_full_scale: float = Field(gt=0)
    temporal_trend_full_scale: float = Field(gt=0)
    minimum_history_windows: int = Field(ge=2)
    weights: FatigueWeights
    score_bands: ScoreBands

    @model_validator(mode="after")
    def validate_always_available_evidence(self) -> "FatiguePolicy":
        if self.weights.baseline_deviation <= 0:
            raise ValueError(
                "Baseline deviation must have positive fatigue evidence weight."
            )
        return self


class WorkloadPolicy(BaseModel):
    """Configured individual session-exposure interpretation."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    window_time_scale_seconds: float = Field(gt=0)
    optimal_min_ratio: float = Field(ge=0)
    elevated_ratio: float = Field(gt=0)
    excessive_ratio: float = Field(gt=0)
    intensity_multipliers: tuple[IntensityMultiplier, ...] = Field(min_length=1)
    default_intensity_multiplier: float = Field(gt=0)

    @field_validator("intensity_multipliers")
    @classmethod
    def validate_intensities(
        cls,
        values: tuple[IntensityMultiplier, ...],
    ) -> tuple[IntensityMultiplier, ...]:
        names = tuple(value.name for value in values)
        if len(set(names)) != len(names) or names != tuple(sorted(names)):
            raise ValueError(
                "Intensity multipliers must have unique, deterministic name ordering."
            )
        return values

    @model_validator(mode="after")
    def validate_ratios(self) -> "WorkloadPolicy":
        if not (
            self.optimal_min_ratio
            < self.elevated_ratio
            < self.excessive_ratio
        ):
            raise ValueError("Workload ratio boundaries must be strictly increasing.")
        return self


class RiskEngineConfig(BaseModel):
    """Complete immutable clinical policy required for one Phase 9 engine."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    schema_version: str = risk_engine_config.RISK_ENGINE_SCHEMA_VERSION
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    left_group_id: str = Field(min_length=1)
    right_group_id: str = Field(min_length=1)
    quadriceps_target_name: str = Field(min_length=1)
    hamstring_target_name: str = Field(min_length=1)
    asymmetry_target_names: tuple[str, ...] = Field(min_length=1)
    fatigue_target_names: tuple[str, ...] = Field(min_length=1)
    asymmetry_policy: AsymmetryPolicy
    muscle_balance_policy: MuscleBalancePolicy
    fatigue_policy: FatiguePolicy
    workload_policy: WorkloadPolicy
    risk_weights: RiskWeights
    risk_score_bands: ScoreBands
    confidence_weights: ConfidenceWeights

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != risk_engine_config.RISK_ENGINE_SCHEMA_VERSION:
            raise ValueError("Unsupported Risk Engine schema version.")
        return value

    @field_validator(
        "asymmetry_target_names",
        "fatigue_target_names",
    )
    @classmethod
    def validate_target_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if (
            any(not value.strip() for value in values)
            or len(set(values)) != len(values)
            or values != tuple(sorted(values))
        ):
            raise ValueError(
                "Risk target names must be unique and deterministically ordered."
            )
        return values

    @model_validator(mode="after")
    def validate_policy(self) -> "RiskEngineConfig":
        if self.left_group_id == self.right_group_id:
            raise ValueError("Risk Engine left and right group IDs must differ.")
        required = {
            self.quadriceps_target_name,
            self.hamstring_target_name,
        }
        if not required.issubset(self.asymmetry_target_names) or not required.issubset(
            self.fatigue_target_names
        ):
            raise ValueError(
                "Primary quadriceps and hamstring targets must participate in "
                "asymmetry and fatigue analysis."
            )
        return self

    @property
    def configuration_hash(self) -> str:
        """Return the canonical identity of the complete clinical policy."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
