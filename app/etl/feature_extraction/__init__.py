"""
Feature Extraction package.

Stage 7 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/FEATURE_EXTRACTION_DESIGN.md.

ExtractedFeatureSet is exported for use elsewhere within app/etl (e.g.
the future Feature Validation stage). It must never be imported outside
app/etl.
"""

from .defaults import default_feature_modules
from .extracted_feature_set import ExtractedFeatureSet
from .extractor import ExtractedFeatureSetConsumer, Extractor
from .feature_module import FeatureModule
from .motion_features import MotionFeatures
from .muscle_features import MuscleFeatures
from .pressure_features import PressureFeatures

__all__ = [
    "Extractor",
    "ExtractedFeatureSetConsumer",
    "ExtractedFeatureSet",
    "FeatureModule",
    "MotionFeatures",
    "PressureFeatures",
    "MuscleFeatures",
    "default_feature_modules",
]
