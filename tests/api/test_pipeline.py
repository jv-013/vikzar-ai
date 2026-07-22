"""End-to-end validation → Phase 8 → Phase 9 API tests."""

from __future__ import annotations

from tests.api.helpers import make_player, make_raw_feature_vector, make_session


def _start(client):
    return client.post(
        "/api/v1/sessions/start",
        json={
            "player": make_player().model_dump(mode="json"),
            "session": make_session().model_dump(mode="json"),
        },
    )


def test_end_to_end_pipeline_calls_phase_eight_then_phase_nine(
    api_context,
) -> None:
    client = api_context["client"]
    assert _start(client).status_code == 201
    vector = make_raw_feature_vector()

    response = client.post(
        "/api/v1/sessions/session-001/feature-vectors",
        json={"feature_vector": vector.model_dump(mode="json")},
        headers={"X-Correlation-ID": "pipeline-trace-001"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert api_context["inference"].calls == 1
    assert len(body["predictions"]) == 2
    assert body["risk_assessment"]["provenance"]["prediction_ids"] == [
        prediction["prediction_id"] for prediction in body["predictions"]
    ]
    assert body["session"]["prediction_count"] == 2
    assert body["synchronization"]["status"] == "disabled"


def test_pipeline_accumulates_local_history_without_uploading_features(
    api_context,
) -> None:
    client = api_context["client"]
    _start(client)
    first = make_raw_feature_vector()
    second = make_raw_feature_vector(
        feature_vector_id="feature-vector-002",
        window_start=1000,
        window_end=2000,
    )
    assert client.post(
        "/api/v1/sessions/session-001/feature-vectors",
        json={"feature_vector": first.model_dump(mode="json")},
    ).status_code == 200
    response = client.post(
        "/api/v1/sessions/session-001/feature-vectors",
        json={"feature_vector": second.model_dump(mode="json")},
    )

    assert response.status_code == 200
    assert len(
        response.json()["risk_assessment"]["provenance"]["prediction_ids"]
    ) == 4
    assert response.json()["session"]["prediction_count"] == 4


def test_invalid_and_mismatched_feature_inputs_fail_closed(api_context) -> None:
    client = api_context["client"]
    _start(client)
    assert client.post(
        "/api/v1/sessions/session-001/feature-vectors",
        json={"feature_vector": {}},
    ).status_code == 422

    vector = make_raw_feature_vector()
    payload = vector.model_dump(mode="json")
    payload["session"]["session_id"] = "other-session"
    response = client.post(
        "/api/v1/sessions/session-001/feature-vectors",
        json={"feature_vector": payload},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PIPELINE_INPUT_REJECTED"


def test_correlation_validation_and_metrics(api_context) -> None:
    client = api_context["client"]
    assert client.get(
        "/metrics",
        headers={"X-Correlation-ID": "bad id with spaces"},
    ).status_code == 400
    assert client.get("/health/live").status_code == 200
    metrics = client.get("/metrics").json()
    assert metrics["requests_total"] >= 1
