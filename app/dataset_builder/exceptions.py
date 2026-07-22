"""Exceptions raised by the offline dataset-building pipeline."""


class DatasetBuilderError(Exception):
    """Base exception for dataset-building failures."""


class DatasetInputError(DatasetBuilderError):
    """Raised when verified-session evidence is incomplete or inconsistent."""


class DatasetStorageError(DatasetBuilderError):
    """Raised when a versioned dataset cannot be persisted or verified."""
