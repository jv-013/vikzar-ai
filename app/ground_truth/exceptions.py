"""Exceptions raised by the offline ground-truth pipeline."""


class GroundTruthError(Exception):
    """Base exception for ground-truth preparation failures."""


class CaptureSessionError(GroundTruthError):
    """Raised when a capture session cannot support verified ground truth."""


class StorageError(GroundTruthError):
    """Raised when a verified session cannot be persisted losslessly."""
