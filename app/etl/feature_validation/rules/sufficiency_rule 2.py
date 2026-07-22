"""
SufficiencyRule: flags a domain's biomarkers when its sample_count
falls below a fraction of the window's own nominal expected sample
count.

See docs/development/FEATURE_VALIDATION_DESIGN.md, Scientific
Rationale, and Decision 029.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from app.etl.feature_extraction import ExtractedFeatureSet

from ..quality import QualityFlag
from ..validation_rule import RuleResult


class SufficiencyRule:
    """
    Flags every biomarker in a domain as under-supported when that
    domain's sample_count (Decision 029) is below a configured fraction
    of the window's own nominal expected sample count.

    Rationale: sample presence alone (what Feature Extraction's own
    gates already guarantee) is a weaker signal than an actual count —
    a biomarker computed from barely enough samples to be
    mathematically defined is not necessarily one that should be
    trusted. minimum_fraction is explicitly a conservative, round,
    provisional starting point (etl_config.MINIMUM_SAMPLE_COUNT_FRACTION,
    default 0.5) — not a statistically validated threshold — the same
    honesty discipline as Calibration's and Filtering's DEV_*
    placeholders. Soft concern (QUESTIONABLE-tier): the value is still
    mathematically well-formed, only under-supported.
    """

    def __init__(self, minimum_fraction: float, nominal_sample_interval_ms: float) -> None:
        if not (0.0 < minimum_fraction <= 1.0):
            raise ValueError(f"minimum_fraction must be in (0.0, 1.0]; got {minimum_fraction!r}.")
        if nominal_sample_interval_ms <= 0:
            raise ValueError("nominal_sample_interval_ms must be positive.")
        self._minimum_fraction = minimum_fraction
        self._nominal_sample_interval_ms = nominal_sample_interval_ms

    def evaluate(self, extracted: ExtractedFeatureSet) -> RuleResult:
        window_duration_ms = extracted.window_end - extracted.window_start
        nominal_count = window_duration_ms / self._nominal_sample_interval_ms
        required = math.ceil(nominal_count * self._minimum_fraction)

        flags: Dict[Tuple[str, str], QualityFlag] = {}
        for domain_name, features in extracted.domains.items():
            count = extracted.sample_counts.get(domain_name, 0)
            if count < required:
                for feature_name in features:
                    flags[(domain_name, feature_name)] = QualityFlag.INSUFFICIENT_SAMPLE_COUNT
        return RuleResult(biomarker_flags=flags)
