from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationReport:
    """
    Stores the result of validating a FeatureVector.
    """

    is_valid: bool = True

    errors: List[str] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)