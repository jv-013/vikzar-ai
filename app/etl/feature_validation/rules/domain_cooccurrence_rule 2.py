"""
DomainCoOccurrenceRule: verifies that biomarkers/domains Feature
Extraction always computes together actually appear together.

See docs/development/FEATURE_VALIDATION_DESIGN.md, Scientific
Rationale.
"""

from __future__ import annotations

from typing import Dict, Mapping, Sequence, Tuple

from app.etl.feature_extraction import ExtractedFeatureSet

from ..quality import QualityFlag, SetQualityObservation
from ..validation_rule import RuleResult

# Biomarker names verified, by reading the actual Feature Extraction
# source, to always be added inside the exact same gate — e.g.
# mean_jerk/peak_jerk are both set inside the same `if jerks:` block in
# MotionFeatures. A violation here can only mean a future Feature
# Extraction regression, not a property of real data.
#
# pressure's loading_rate/impulse were deliberately NOT included here,
# despite looking co-gated at a glance: PressureFeatures sets
# features["impulse"] unconditionally once len(load_series) >= 2, but
# features["loading_rate"] only `if rates:` (an extra, narrower gate —
# rates stays empty, and impulse stays exactly 0.0, whenever every
# consecutive frame pair shares the same reference_timestamp). That
# degenerate-but-structurally-possible case would make impulse present
# without loading_rate on entirely legitimate data — asserting
# co-occurrence here would produce a false QUESTIONABLE flag. See
# FEATURE_VALIDATION_DESIGN.md.
_BIOMARKER_COOCCURRENCE_GROUPS: Mapping[str, Sequence[Sequence[str]]] = {
    "motion": (("mean_jerk", "peak_jerk"),),
}

# motion and pressure both read exclusively from the "primary_motion"
# reading (see MotionFeatures/PressureFeatures docstrings) — if that
# reading existed for a frame, both domains had a chance to compute
# something from it. One present without the other is unexpected given
# today's hardware (every V1 Smart Pod has both IMU and FSR); revisit
# if a future Smart Pod variant genuinely omits one.
_DOMAIN_COOCCURRENCE_GROUP: Tuple[str, str] = ("motion", "pressure")


class DomainCoOccurrenceRule:
    """
    Flags a biomarker (or domain) that Feature Extraction's own
    internal gating guarantees should never appear alone, when it does.

    Rationale: verifies Feature Extraction's own contract still holds —
    the "final quality gate" checking upstream, not a re-derivation of
    new science. Cannot trigger on correct Feature Extraction output
    today; exists to catch a future regression. Soft concern
    (QUESTIONABLE-tier) — the value itself is still mathematically
    well-formed, only its context is anomalous.
    """

    def evaluate(self, extracted: ExtractedFeatureSet) -> RuleResult:
        flags: Dict[Tuple[str, str], QualityFlag] = {}
        observations = []

        for domain_name, groups in _BIOMARKER_COOCCURRENCE_GROUPS.items():
            features = extracted.domains.get(domain_name)
            if not features:
                continue
            for group in groups:
                present = [name for name in group if name in features]
                if present and len(present) != len(group):
                    for name in present:
                        flags[(domain_name, name)] = QualityFlag.EXPECTED_COOCCURRING_BIOMARKER_MISSING

        first_domain, second_domain = _DOMAIN_COOCCURRENCE_GROUP
        first_present = first_domain in extracted.domains
        second_present = second_domain in extracted.domains
        if first_present != second_present:
            present_domain = first_domain if first_present else second_domain
            absent_domain = second_domain if first_present else first_domain
            observations.append(
                SetQualityObservation(
                    flag=QualityFlag.EXPECTED_COOCCURRING_BIOMARKER_MISSING,
                    domain=absent_domain,
                    rationale=(
                        f"'{present_domain}' domain is present but '{absent_domain}' "
                        f"is not — both are sourced from the same 'primary_motion' "
                        f"reading and are expected to co-occur on today's hardware."
                    ),
                )
            )

        return RuleResult(biomarker_flags=flags, set_observations=tuple(observations))
