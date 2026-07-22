"""Unit tests for FiniteValueRule."""

from __future__ import annotations

import math

from app.etl.feature_validation.quality import QualityFlag
from app.etl.feature_validation.rules.finite_value_rule import FiniteValueRule

from .helpers import make_extracted_feature_set


def test_flags_nan_value() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": math.nan}})

    result = FiniteValueRule().evaluate(extracted)

    assert result.biomarker_flags[("motion", "peak_resultant_acceleration")] == QualityFlag.NON_FINITE_VALUE


def test_flags_infinite_value() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": math.inf}})

    result = FiniteValueRule().evaluate(extracted)

    assert result.biomarker_flags[("motion", "peak_resultant_acceleration")] == QualityFlag.NON_FINITE_VALUE


def test_does_not_flag_finite_values() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 5.0}})

    result = FiniteValueRule().evaluate(extracted)

    assert result.biomarker_flags == {}
