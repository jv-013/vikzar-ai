"""Custom exceptions used by the AI FeatureVector validation module."""

from app.validation.report import ValidationIssue, ValidationReport


class ValidationError(Exception):
    """Base class for validation-related exceptions.

    Parameters:
        message: Human-readable error message.
        report: Optional validation report associated with the failure.
        issues: Optional structured validation issues.

    Returns:
        An exception carrying structured validation context.

    Exceptions:
        None.
    """

    def __init__(
        self,
        message: str,
        *,
        report: ValidationReport | None = None,
        issues: list[ValidationIssue] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.report = report
        self.issues = issues or []

    def to_dict(self) -> dict[str, object]:
        """Return a serializable representation of the exception.

        Parameters:
            None.

        Returns:
            Dictionary containing the exception class, message, and
            structured validation context.

        Exceptions:
            None.
        """

        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "report": _model_to_dict(self.report) if self.report else None,
            "issues": [_model_to_dict(issue) for issue in self.issues],
        }


class FeatureValidationError(ValidationError):
    """Raised when a parsed FeatureVector fails semantic validation."""


class SchemaValidationError(ValidationError):
    """Raised when input cannot be parsed as a FeatureVector schema."""


class MissingFieldError(ValidationError):
    """Raised when a required field or section is missing."""


class InvalidValueError(ValidationError):
    """Raised when a field contains an invalid value."""


def _model_to_dict(model: object) -> dict[str, object]:
    """Convert a Pydantic model to a dictionary across Pydantic versions.

    Parameters:
        model: Pydantic model instance.

    Returns:
        Dictionary representation of the model.

    Exceptions:
        AttributeError: Raised if the object is not a Pydantic-like model.
    """

    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    return model.dict()  # type: ignore[attr-defined, no-any-return]
