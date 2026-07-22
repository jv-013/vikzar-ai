"""Exceptions raised by the offline evaluation framework."""


class EvaluationError(Exception):
    """Base exception for evaluation failures."""


class PredictionSetError(EvaluationError):
    """Raised when supplied predictions and ground truth cannot be evaluated."""


class EvaluationStorageError(EvaluationError):
    """Raised when an immutable evaluation report cannot be persisted or verified."""
