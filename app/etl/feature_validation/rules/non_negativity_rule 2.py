"""
NonNegativityRule: biomarkers that are non-negative by construction of
their own formula must be >= 0.

See docs/development/FEATURE_VALIDATION_DESIGN.md, Scientific
Rationale.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping, Tuple

from app.etl.feature_extraction import ExtractedFeatureSet

from ..quality import QualityFlag
from ..validation_rule import RuleResult

# Explicit, documented, per-domain set of biomarkers that are
# non-negative by the mathematical definition of their own formula —
# not a physical-plausibility judgment, a definitional fact:
#   - resultant/magnitude values (sqrt(x^2+y^2+z^2)) are >= 0 always.
#   - RMS (sqrt(mean(x^2))) and MAV (mean(|x|)) are >= 0 for any real x.
#   - cadence_per_minute is a peak-count divided by a positive duration.
#   - impulse assumes non-negative load values (true today given
#     non-negative raw FSR counts and identity calibration — a
#     documented calibration-state assumption, not a pure-math
#     guarantee like the others in this set).
# loading_rate is deliberately excluded: PressureFeatures reports
# max(rate-of-change), which is legitimately negative whenever load is
# net-decreasing across the whole window (e.g. a window capturing only
# the unloading phase of a step) — asserting non-negativity for it
# would incorrectly reject real data.
_NON_NEGATIVE_BIOMARKERS: Mapping[str, FrozenSet[str]] = {
    "motion": frozenset(
        {
            "peak_resultant_acceleration",
            "mean_resultant_acceleration",
            "rms_resultant_acceleration",
            "peak_angular_velocity",
            "mean_jerk",
            "peak_jerk",
            "cadence_per_minute",
        }
    ),
    "pressure": frozenset({"peak_load", "mean_load", "rms_load", "impulse"}),
    "muscle": frozenset(
        {
            "quadriceps_rms",
            "quadriceps_mean_absolute_value",
            "hamstring_rms",
            "hamstring_mean_absolute_value",
        }
    ),
}


class NonNegativityRule:
    """
    Flags a biomarker known to be non-negative by construction if its
    value is negative.

    Rationale: unit-independent — these are definitional facts about
    each formula (a magnitude, an RMS, an MAV, a count-over-duration),
    true regardless of calibration state. A violation indicates a
    computation bug. Hard violation (REJECTED-tier).
    """

    def evaluate(self, extracted: ExtractedFeatureSet) -> RuleResult:
        flags: Dict[Tuple[str, str], QualityFlag] = {}
        for domain_name, known_non_negative in _NON_NEGATIVE_BIOMARKERS.items():
            features = extracted.domains.get(domain_name, {})
            for feature_name in known_non_negative:
                value = features.get(feature_name)
                if value is not None and value < 0:
                    flags[(domain_name, feature_name)] = (
                        QualityFlag.NEGATIVE_VALUE_IMPOSSIBLE_BY_DEFINITION
                    )
        return RuleResult(biomarker_flags=flags)
