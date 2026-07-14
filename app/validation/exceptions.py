"""
Custom exceptions used by the Validation Engine.
"""


class ValidationError(Exception):
    """
    Base class for all validation-related exceptions.
    """
    pass


class FeatureValidationError(ValidationError):
    """
    Raised when a FeatureVector fails validation.
    """
    pass


class SchemaValidationError(ValidationError):
    """
    Raised when the FeatureVector schema is invalid.
    """
    pass


class MissingFieldError(ValidationError):
    """
    Raised when a required field is missing.
    """
    pass


class InvalidValueError(ValidationError):
    """
    Raised when a field contains an invalid value.
    """
    pass