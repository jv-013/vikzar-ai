"""Exceptions raised by permanent benchmark model adapters."""


class BenchmarkModelError(Exception):
    """Base exception for benchmark training, prediction, and loading failures."""


class BenchmarkConfigurationError(BenchmarkModelError):
    """Raised when an adapter and immutable experiment specification disagree."""


class BenchmarkDataError(BenchmarkModelError):
    """Raised when model input violates the declared Phase 3 schema."""


class BenchmarkSerializationError(BenchmarkModelError):
    """Raised when a model artifact is invalid or fails checksum verification."""
