"""
Default FeatureModule registry.

See docs/development/FEATURE_EXTRACTION_DESIGN.md.
"""

from __future__ import annotations

from typing import Dict

from .feature_module import FeatureModule
from .motion_features import MotionFeatures
from .muscle_features import MuscleFeatures
from .pressure_features import PressureFeatures


def default_feature_modules() -> Dict[str, FeatureModule]:
    """
    Build the default domain-name -> FeatureModule registry.

    Unlike Calibration's or Filtering's registries (keyed by channel
    name, since those stages act per-channel), this one is keyed by
    domain name and needs no per-group or per-channel instance
    management at all: every FeatureModule is stateless and operates on
    a whole Window at once, so one shared instance per domain serves
    every synchronization group and every call.

    Returns:
        A new dict mapping each domain name to its FeatureModule
        instance. A fresh dict is returned on every call; callers that
        construct an Extractor own their own copy.
    """
    return {
        "motion": MotionFeatures(),
        "pressure": PressureFeatures(),
        "muscle": MuscleFeatures(),
    }
