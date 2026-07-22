"""Expected Phase 10 application and integration failures."""

from __future__ import annotations


class APIIntegrationError(Exception):
    """Base class for expected integration failures."""


class APIConfigurationError(APIIntegrationError):
    """Raised when startup configuration or dependencies are invalid."""


class AuthenticationError(APIIntegrationError):
    """Raised when an authentication hook rejects a request."""


class SessionNotFoundError(APIIntegrationError):
    """Raised when a session ID is unavailable locally."""


class SessionConflictError(APIIntegrationError):
    """Raised when a deterministic lifecycle transition is invalid."""


class SessionRecoveryError(APIIntegrationError):
    """Raised when a local checkpoint cannot be verified or recovered."""


class PipelineOrchestrationError(APIIntegrationError):
    """Raised when frozen phases cannot be orchestrated safely."""


class FirebaseSynchronizationError(APIIntegrationError):
    """Raised internally when optional Firebase transport is unavailable."""
