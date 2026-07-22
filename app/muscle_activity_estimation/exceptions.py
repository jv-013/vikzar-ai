"""Domain-specific exceptions for muscle activity estimation."""


class MuscleActivityEstimationError(Exception):
    """Base exception for muscle activity estimation failures."""


class MuscleEstimationInputError(MuscleActivityEstimationError):
    """Raised when validated pipeline inputs do not identify the same vector."""


class MuscleEstimationModelExecutionError(MuscleActivityEstimationError):
    """Raised when an injected model implementation cannot execute."""


class MuscleEstimationOutputError(MuscleActivityEstimationError):
    """Raised when an injected model returns an invalid output contract."""
