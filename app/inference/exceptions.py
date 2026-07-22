"""Exceptions raised by the deterministic Phase 8 inference boundary."""

from __future__ import annotations


class InferenceError(Exception):
    """Base class for every expected Phase 8 failure."""


class InferenceConfigurationError(InferenceError):
    """Raised when deterministic runtime configuration is invalid."""


class ModelApprovalError(InferenceError):
    """Raised when Phase 7 evidence does not approve a model for inference."""


class ModelIntegrityError(InferenceError):
    """Raised when immutable model evidence fails checksum verification."""


class ModelCompatibilityError(InferenceError):
    """Raised when an approved model cannot consume the runtime schema."""


class ModelLoadError(InferenceError):
    """Raised when approved production model evidence cannot be loaded."""


class InferenceInputError(InferenceError):
    """Raised when a validated feature vector cannot satisfy the model schema."""


class InferenceOutputError(InferenceError):
    """Raised when a model emits malformed or non-finite predictions."""
