"""Expected failures at the deterministic Phase 9 risk boundary."""

from __future__ import annotations


class RiskEngineError(Exception):
    """Base class for all expected Phase 9 failures."""


class RiskConfigurationError(RiskEngineError):
    """Raised when a clinical policy configuration is invalid."""


class RiskInputError(RiskEngineError):
    """Raised when Phase 8 evidence or supplied metadata is inconsistent."""


class RiskComputationError(RiskEngineError):
    """Raised when a deterministic component cannot produce a valid score."""


class RiskOutputError(RiskEngineError):
    """Raised when a risk assessment fails its immutable output contract."""
