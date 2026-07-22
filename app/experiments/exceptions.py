"""Exceptions raised by the offline experiment framework."""


class ExperimentError(Exception):
    """Base exception for experiment-framework failures."""


class DuplicateExperimentError(ExperimentError):
    """Raised when a completed or active experiment identifier is reused."""


class ExperimentExecutionError(ExperimentError):
    """Raised when a model adapter cannot complete an experiment execution."""


class ExperimentLockError(ExperimentError):
    """Raised when an experiment ID is already protected by an active lock."""


class ExperimentCompatibilityError(ExperimentError):
    """Raised when candidate, dataset, specification, or report lineage disagrees."""


class ExperimentStorageError(ExperimentError):
    """Raised when local experiment evidence cannot be persisted or verified."""
