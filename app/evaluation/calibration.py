"""Confidence calibration calculations for continuous prediction submissions."""

from __future__ import annotations

from .contracts import CalibrationResult, EvaluationSlice


def calculate_calibration(
    *,
    target_name: str,
    evaluation_slice: EvaluationSlice | None,
    actual: tuple[float, ...],
    predicted: tuple[float, ...],
    confidence: tuple[float | None, ...],
    absolute_error_tolerance: float,
) -> CalibrationResult:
    """Compare reported confidence with agreement inside a declared error tolerance."""

    confident = tuple(
        (truth, estimate, certainty)
        for truth, estimate, certainty in zip(actual, predicted, confidence)
        if certainty is not None
    )
    if not confident:
        return CalibrationResult(
            target_name=target_name,
            slice=evaluation_slice,
            available=False,
            confidence_sample_count=0,
        )
    mean_confidence = sum(item[2] for item in confident) / len(confident)
    empirical_agreement = sum(
        abs(estimate - truth) <= absolute_error_tolerance
        for truth, estimate, _ in confident
    ) / len(confident)
    return CalibrationResult(
        target_name=target_name,
        slice=evaluation_slice,
        available=True,
        confidence_sample_count=len(confident),
        mean_confidence=mean_confidence,
        empirical_agreement=empirical_agreement,
        calibration_gap=abs(mean_confidence - empirical_agreement),
    )
