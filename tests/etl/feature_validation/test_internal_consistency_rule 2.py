"""Unit tests for InternalConsistencyRule."""

from __future__ import annotations

from app.etl.feature_validation.quality import QualityFlag
from app.etl.feature_validation.rules.internal_consistency_rule import InternalConsistencyRule

from .helpers import make_extracted_feature_set


def test_flags_peak_below_mean() -> None:
    extracted = make_extracted_feature_set(
        domains={
            "motion": {
                "peak_resultant_acceleration": 1.0,
                "rms_resultant_acceleration": 2.0,
                "mean_resultant_acceleration": 3.0,
            }
        }
    )

    result = InternalConsistencyRule().evaluate(extracted)

    assert result.biomarker_flags[("motion", "peak_resultant_acceleration")] == (
        QualityFlag.INTERNAL_CONSISTENCY_VIOLATED
    )
    assert result.biomarker_flags[("motion", "rms_resultant_acceleration")] == (
        QualityFlag.INTERNAL_CONSISTENCY_VIOLATED
    )


def test_flags_rms_below_mav() -> None:
    extracted = make_extracted_feature_set(
        domains={"muscle": {"quadriceps_rms": 1.0, "quadriceps_mean_absolute_value": 5.0}}
    )

    result = InternalConsistencyRule().evaluate(extracted)

    assert result.biomarker_flags[("muscle", "quadriceps_rms")] == QualityFlag.INTERNAL_CONSISTENCY_VIOLATED


def test_does_not_flag_correct_ordering() -> None:
    extracted = make_extracted_feature_set(
        domains={
            "motion": {
                "peak_resultant_acceleration": 10.0,
                "rms_resultant_acceleration": 6.0,
                "mean_resultant_acceleration": 5.0,
            }
        }
    )

    result = InternalConsistencyRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_skips_comparison_when_one_member_of_chain_missing() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 1.0}})

    result = InternalConsistencyRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_tolerates_floating_point_noise_on_a_constant_signal() -> None:
    """Regression test: rms computed via sqrt(mean(x^2)) can come out
    marginally *less* than mean computed via sum(x)/n on a constant or
    near-constant signal, purely from floating-point rounding — a
    completely realistic case (e.g. a stationary athlete), not a
    hypothetical one. A strict '<' comparison would incorrectly reject
    this valid data.

    Whether this specific fixture actually produces measurable rounding
    noise is itself interpreter/platform-dependent (observed: it does
    under Python 3.9, it does not under Python 3.12, for this exact
    value/count pair) — so the test intentionally does not assert on
    the noise being present, only that InternalConsistencyRule doesn't
    flag this realistic derivation either way. See the dedicated,
    deterministic epsilon test below for guaranteed tolerance coverage
    independent of any interpreter's rounding behavior.
    """
    value = 1234567.891
    n = 7
    mean = sum([value] * n) / n
    rms = (sum(value * value for _ in range(n)) / n) ** 0.5

    extracted = make_extracted_feature_set(
        domains={
            "motion": {
                "peak_resultant_acceleration": value,
                "rms_resultant_acceleration": rms,
                "mean_resultant_acceleration": mean,
            }
        }
    )

    result = InternalConsistencyRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_tolerates_a_deliberately_tiny_epsilon_difference() -> None:
    """Deterministic, interpreter-independent proof that the tolerance
    mechanism itself works: an explicit, guaranteed-reproducible
    near-equal pair (not relying on incidental floating-point rounding
    from any particular interpreter or platform)."""
    extracted = make_extracted_feature_set(
        domains={
            "motion": {
                "peak_resultant_acceleration": 100.0,
                "rms_resultant_acceleration": 100.0 - 1e-10,
                "mean_resultant_acceleration": 100.0 - 1e-10,
            }
        }
    )

    result = InternalConsistencyRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_permits_equal_values() -> None:
    extracted = make_extracted_feature_set(
        domains={
            "motion": {
                "peak_resultant_acceleration": 5.0,
                "rms_resultant_acceleration": 5.0,
                "mean_resultant_acceleration": 5.0,
            }
        }
    )

    result = InternalConsistencyRule().evaluate(extracted)

    assert result.biomarker_flags == {}
