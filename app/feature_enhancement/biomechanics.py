"""Biomechanics-oriented feature enhancement."""

from typing import Any, Dict

from .feature_enhancer import FeatureEnhancer


class BiomechanicsEnhancer(FeatureEnhancer):
    """Adds biomechanical context to feature representations."""

    def enhance(self, features: Dict[str, Any]) -> Dict[str, Any]:
        return {**features, "biomechanics_context": True}
