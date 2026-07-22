"""Exceptions raised by the offline Phase 7 production model pipeline."""


class ProductionModelError(Exception):
    """Base exception for production model training and evidence failures."""


class ProductionConfigurationError(ProductionModelError):
    """Raised when production configuration or experiment lineage disagrees."""


class ProductionDataError(ProductionModelError):
    """Raised when Phase 3 data does not match the declared production schema."""


class ProductionSerializationError(ProductionModelError):
    """Raised when a production artifact cannot be verified or loaded."""


class ProductionRegistryError(ProductionModelError):
    """Raised when immutable production model registration fails."""


class ProductionSelectionError(ProductionModelError):
    """Raised when benchmark comparison evidence is incomplete or incompatible."""
