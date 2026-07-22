"""Factory for permanent production model adapters."""

from .configuration import ProductionModelConfig
from .interface import ProductionModelAdapter
from .model import DeterministicMLPRegressorAdapter


class ProductionModelFactory:
    """Construct the supported versioned production adapter."""

    @staticmethod
    def create(config: ProductionModelConfig) -> ProductionModelAdapter:
        """Return the deterministic production MLP for an immutable configuration."""

        return DeterministicMLPRegressorAdapter(config)
