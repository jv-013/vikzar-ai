"""Shared deterministic mathematical rules with no clinical constants."""

from __future__ import annotations

from .configuration import RatioBands, ScoreBands
from .contracts import (
    AsymmetryStatus,
    FatigueLevel,
    MuscleBalanceStatus,
    RiskLevel,
)


def clamp_score(value: float) -> float:
    """Clamp a calculated indicator to the public 0–100 scale."""

    return min(100.0, max(0.0, float(value)))


def ratio_score(value: float, critical_threshold: float) -> float:
    """Map a non-negative ratio linearly to 100 at its configured critical point."""

    return clamp_score(100.0 * value / critical_threshold)


def risk_level(score: float, bands: ScoreBands) -> RiskLevel:
    if score >= bands.critical:
        return RiskLevel.CRITICAL
    if score >= bands.high:
        return RiskLevel.HIGH
    if score >= bands.watch:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def fatigue_level(score: float, bands: ScoreBands) -> FatigueLevel:
    if score >= bands.critical:
        return FatigueLevel.SEVERE
    if score >= bands.high:
        return FatigueLevel.HIGH
    if score >= bands.watch:
        return FatigueLevel.ELEVATED
    return FatigueLevel.LOW


def asymmetry_status(
    ratio: float,
    bands: RatioBands,
) -> AsymmetryStatus:
    if ratio >= bands.critical:
        return AsymmetryStatus.CRITICAL
    if ratio >= bands.high:
        return AsymmetryStatus.HIGH
    if ratio >= bands.watch:
        return AsymmetryStatus.WATCH
    return AsymmetryStatus.BALANCED


def muscle_balance_status(
    score: float,
    bands: ScoreBands,
) -> MuscleBalanceStatus:
    if score >= bands.critical:
        return MuscleBalanceStatus.CRITICAL
    if score >= bands.high:
        return MuscleBalanceStatus.HIGH
    if score >= bands.watch:
        return MuscleBalanceStatus.WATCH
    return MuscleBalanceStatus.WITHIN_RANGE
