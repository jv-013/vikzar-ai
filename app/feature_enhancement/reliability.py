"""Reliability-based feature enhancement."""

from typing import Any, Dict

from .feature_enhancer import FeatureEnhancer


class ReliabilityEnhancer(FeatureEnhancer):
    """Adds reliability signals to feature vectors."""

    def enhance(self, features: Dict[str, Any]) -> Dict[str, Any]:
        return {**features, "reliability_context": True}
