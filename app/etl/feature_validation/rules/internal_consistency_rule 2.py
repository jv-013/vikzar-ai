"""
InternalConsistencyRule: checks mathematically-required orderings
between co-occurring biomarkers in the same domain.

See docs/development/FEATURE_VALIDATION_DESIGN.md, Scientific
Rationale.
"""

from __future__ import annotations

import math
from typing import Dict, List, Mapping, Sequence, Tuple

from app.etl.feature_extraction import ExtractedFeatureSet

from ..quality import QualityFlag
from ..validation_rule import RuleResult

# Standard library default for math.isclose — a well-established
# floating-point comparison convention, not a fabricated scientific
# threshold. Needed because rms >= mean (and similar inequalities) are
# only exactly true in real-number arithmetic; computed via different
# operation sequences (sqrt(mean(x^2)) vs sum(x)/n), floating-point
# rounding can make rms marginally *less* than mean on a constant or
# near-constant signal (e.g. a stationary athlete, or an all-zero
# channel) — a completely realistic case, verified empirically, not a
# hypothetical edge case.
_RELATIVE_TOLERANCE = 1e-9

# Each chain is a sequence of biomarker names that must appear in
# non-increasing order (chain[0] >= chain[1] >= ...) whenever all
# members are present. These are provable inequalities, not fabricated
# thresholds:
#   - max(x) >= RMS(x) >= mean(x) for any non-negative real sequence x
#     (RMS <= max because each term is <= max; RMS >= mean is the
#     standard QM-AM inequality). Motion's resultant values and
#     pressure's total-load values are non-negative — motion's
#     provably so (they are vector magnitudes), pressure's by the
#     documented calibration-state assumption in non_negativity_rule.py.
#   - RMS(x) >= MAV(x) = mean(|x|) for any real sequence x (a standard
#     Cauchy-Schwarz-type inequality) — holds for muscle's EMG values
#     regardless of sign.
#   - peak_jerk >= mean_jerk, since MotionFeatures already takes
#     abs(rate-of-change) before both are computed (a non-negative
#     peak-vs-mean pair, same as the resultant-value chains).
_CONSISTENCY_CHAINS: Mapping[str, Sequence[Sequence[str]]] = {
    "motion": (
        ("peak_resultant_acceleration", "rms_resultant_acceleration", "mean_resultant_acceleration"),
        ("peak_jerk", "mean_jerk"),
    ),
    "pressure": (("peak_load", "rms_load", "mean_load"),),
    "muscle": (
        ("quadriceps_rms", "quadriceps_mean_absolute_value"),
        ("hamstring_rms", "hamstring_mean_absolute_value"),
    ),
}


class InternalConsistencyRule:
    """
    Flags biomarkers that violate a mathematically-required ordering
    with a co-occurring biomarker in the same domain (e.g. peak less
    than mean), tolerant of floating-point noise (see
    _RELATIVE_TOLERANCE above) so a constant or near-constant signal
    does not produce a false REJECTED status.

    Rationale: unit-independent — these orderings are provable
    inequalities (see module docstring), true regardless of
    calibration state. A violation indicates a computation bug. Hard
    violation (REJECTED-tier).
    """

    def evaluate(self, extracted: ExtractedFeatureSet) -> RuleResult:
        flags: Dict[Tuple[str, str], QualityFlag] = {}
        for domain_name, chains in _CONSISTENCY_CHAINS.items():
            features = extracted.domains.get(domain_name)
            if not features:
                continue
            for chain in chains:
                self._check_chain(domain_name, chain, features, flags)
        return RuleResult(biomarker_flags=flags)

    def _check_chain(
        self,
        domain_name: str,
        chain: Sequence[str],
        features: Mapping[str, float],
        flags: Dict[Tuple[str, str], QualityFlag],
    ) -> None:
        present: List[str] = [name for name in chain if name in features]
        for earlier_name, later_name in zip(present, present[1:]):
            earlier_value = features[earlier_name]
            later_value = features[later_name]
            if earlier_value < later_value and not math.isclose(
                earlier_value, later_value, rel_tol=_RELATIVE_TOLERANCE
            ):
                flags[(domain_name, earlier_name)] = QualityFlag.INTERNAL_CONSISTENCY_VIOLATED
                flags[(domain_name, later_name)] = QualityFlag.INTERNAL_CONSISTENCY_VIOLATED
