"""
Regression protection: app.etl.feature_validation's quality vocabulary
and app.schemas.quality_info's AI-facing mirror of it must stay in
sync, member-for-member.

Publisher translates via QualityFlagInfo(flag.value) /
QualityStatusInfo(status.value) (see Publisher._translate_quality) —
if a future ValidationRule introduces a new QualityFlag without a
matching QualityFlagInfo member, that translation raises ValueError at
runtime, on exactly the cycle carrying the new flag. This test fails
loudly at test time instead, whenever the two vocabularies drift apart.
"""

from __future__ import annotations

from app.etl.feature_validation import QualityFlag, QualityStatus
from app.schemas.quality_info import QualityFlagInfo, QualityStatusInfo


def test_quality_flag_values_match_exactly() -> None:
    etl_values = {flag.value for flag in QualityFlag}
    schema_values = {flag.value for flag in QualityFlagInfo}
    assert etl_values == schema_values


def test_quality_status_values_match_exactly() -> None:
    etl_values = {status.value for status in QualityStatus}
    schema_values = {status.value for status in QualityStatusInfo}
    assert etl_values == schema_values
