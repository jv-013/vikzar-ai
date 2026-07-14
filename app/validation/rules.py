"""
Validation rules for FeatureVector fields.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ValidationRule:
    """
    Represents a single validation rule.
    """

    name: str
    validator: Callable[[Any], bool]
    error_message: str


# Generic reusable rules
POSITIVE_NUMBER = ValidationRule(
    name="positive_number",
    validator=lambda x: x is not None and x >= 0,
    error_message="Value must be greater than or equal to 0."
)

PERCENTAGE = ValidationRule(
    name="percentage",
    validator=lambda x: x is not None and 0 <= x <= 100,
    error_message="Value must be between 0 and 100."
)

CONFIDENCE_SCORE = ValidationRule(
    name="confidence_score",
    validator=lambda x: x is not None and 0 <= x <= 1,
    error_message="Confidence score must be between 0 and 1."
)

NON_EMPTY_STRING = ValidationRule(
    name="non_empty_string",
    validator=lambda x: isinstance(x, str) and len(x.strip()) > 0,
    error_message="String cannot be empty."
)