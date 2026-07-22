"""Unit tests for validation exceptions."""

from app.validation.exceptions import FeatureValidationError
from app.validation.report import ValidationReport


def test_validation_exception_to_dict_includes_report_and_issues() -> None:
    """Validation exceptions expose structured context for API callers."""

    report = ValidationReport()
    report.add_error(
        code="VAL_TEST",
        field_path="feature_vector_id",
        message="Example validation failure.",
    )

    exc = FeatureValidationError(
        "RawFeatureVector failed validation.",
        report=report,
        issues=report.errors,
    )

    payload = exc.to_dict()

    assert payload["error_type"] == "FeatureValidationError"
    assert payload["message"] == "RawFeatureVector failed validation."
    assert payload["report"] is not None
    assert payload["issues"] == [
        {
            "code": "VAL_TEST",
            "field_path": "feature_vector_id",
            "message": "Example validation failure.",
            "severity": "error",
        }
    ]
