"""Structured logging, standardized errors, and body-limit tests."""

from __future__ import annotations

import json
import logging

from app.api.logging import StructuredJSONFormatter, correlation_id_context


def test_structured_logging_contains_trace_without_secret_fields() -> None:
    formatter = StructuredJSONFormatter()
    token = correlation_id_context.set("trace-001")
    try:
        record = logging.LogRecord(
            "app.api",
            logging.INFO,
            __file__,
            1,
            "request complete",
            (),
            None,
        )
        record.event = "request.completed"
        record.path = "/health/live"
        payload = json.loads(formatter.format(record))
    finally:
        correlation_id_context.reset(token)

    assert payload["correlation_id"] == "trace-001"
    assert payload["event"] == "request.completed"
    assert "authorization" not in payload


def test_standardized_not_found_and_validation_errors(api_context) -> None:
    client = api_context["client"]
    response = client.get(
        "/api/v1/sessions/missing",
        headers={"X-Correlation-ID": "trace-error-001"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert response.json()["error"]["correlation_id"] == "trace-error-001"

    validation = client.post("/api/v1/sessions/start", json={})
    assert validation.status_code == 422
    assert validation.json()["error"]["code"] == "API_VALIDATION_FAILED"


def test_request_body_limit_rejects_before_pipeline(api_context) -> None:
    response = api_context["client"].post(
        "/api/v1/sessions/start",
        content=b"x" * 1_000_001,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "API_REQUEST_TOO_LARGE"
