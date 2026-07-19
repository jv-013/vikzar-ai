"""Domain-specific exceptions for contextual knowledge retrieval."""


class LookupError(Exception):
    """Base exception for Lookup Engine failures.

    Parameters:
        message: Human-readable failure description.

    Returns:
        A Lookup Engine domain exception.

    Exceptions:
        None.
    """


class PositionKnowledgeNotFoundError(LookupError):
    """Raised when a validated player position has no configured knowledge profile."""


class InjuryKnowledgeNotFoundError(LookupError):
    """Raised when supplied injury context has no configured knowledge profile."""


class KnowledgeReferenceNotFoundError(LookupError):
    """Raised when a configured profile points to unavailable knowledge."""
