"""
FiniteValueRule: every biomarker value must be finite.

See docs/development/FEATURE_VALIDATION_DESIGN.md, Scientific
Rationale.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from app.etl.feature_extraction import ExtractedFeatureSet

from ..quality import QualityFlag
from ..validation_rule import RuleResult


class FiniteValueRule:
    """
    Flags any biomarker whose value is NaN or +/-Infinity.

    Rationale: unit-independent — true regardless of calibration state.
    A non-finite value indicates a computation bug or corrupted input,
    never a legitimate measurement. Hard violation (REJECTED-tier).
    """

    def evaluate(self, extracted: ExtractedFeatureSet) -> RuleResult:
        flags: Dict[Tuple[str, str], QualityFlag] = {}
        for domain_name, features in extracted.domains.items():
            for feature_name, value in features.items():
                if not math.isfinite(value):
                    flags[(domain_name, feature_name)] = QualityFlag.NON_FINITE_VALUE
        return RuleResult(biomarker_flags=flags)
