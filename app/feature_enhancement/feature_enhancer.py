"""Base feature enhancement interface."""

from typing import Any, Dict


class FeatureEnhancer:
    """Base class for feature enrichment strategies."""

    def enhance(self, features: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
