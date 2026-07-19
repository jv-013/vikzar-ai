"""Unit tests for NonNegativityRule."""

from __future__ import annotations

from app.etl.feature_validation.quality import QualityFlag
from app.etl.feature_validation.rules.non_negativity_rule import NonNegativityRule

from .helpers import make_extracted_feature_set


def test_flags_negative_value_for_known_non_negative_biomarker() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": -1.0}})

    result = NonNegativityRule().evaluate(extracted)

    assert (
        result.biomarker_flags[("motion", "peak_resultant_acceleration")]
        == QualityFlag.NEGATIVE_VALUE_IMPOSSIBLE_BY_DEFINITION
    )


def test_does_not_flag_zero_or_positive_values() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"peak_resultant_acceleration": 0.0}})

    result = NonNegativityRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_does_not_flag_negative_loading_rate() -> None:
    """loading_rate is deliberately excluded from the known-non-negative
    set — it can legitimately be negative for a net-unloading window."""
    extracted = make_extracted_feature_set(domains={"pressure": {"loading_rate": -50.0}})

    result = NonNegativityRule().evaluate(extracted)

    assert result.biomarker_flags == {}


def test_does_not_flag_unrecognized_biomarker_names() -> None:
    extracted = make_extracted_feature_set(domains={"motion": {"some_future_biomarker": -1.0}})

    result = NonNegativityRule().evaluate(extracted)

    assert result.biomarker_flags == {}
