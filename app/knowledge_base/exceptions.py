"""Exceptions raised by the Vikzar AI knowledge base."""


class KnowledgeBaseError(Exception):
    """Base exception for knowledge-base failures.

    Parameters:
        message: Human-readable failure description.

    Returns:
        A domain-specific exception instance.

    Exceptions:
        None.
    """


class KnowledgeBaseDataError(KnowledgeBaseError):
    """Raised when packaged knowledge data is missing or scientifically invalid."""
