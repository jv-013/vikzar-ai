"""Personalization-based feature enhancement."""

from typing import Any, Dict

from .feature_enhancer import FeatureEnhancer


class PersonalizationEnhancer(FeatureEnhancer):
    """Adds user or athlete-specific adjustments to features."""

    def enhance(self, features: Dict[str, Any]) -> Dict[str, Any]:
        return {**features, "personalized": True}
