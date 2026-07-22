"""Immutable and deterministic Phase 8 contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.inference import InferenceRequest, InferenceRuntimeConfig


def test_runtime_configuration_is_immutable_and_deterministic() -> None:
    first = InferenceRuntimeConfig()
    second = InferenceRuntimeConfig()

    assert first.configuration_hash == second.configuration_hash
    with pytest.raises(ValidationError):
        first.max_batch_size = 1  # type: ignore[misc]


def test_prediction_contract_is_immutable_and_self_verifying(phase8_context) -> None:
    prediction = phase8_context.engine().predict(phase8_context.feature_vector)

    assert prediction.checksum == prediction.calculate_checksum(
        prediction.predictions,
        prediction.metadata,
    )
    with pytest.raises(ValidationError):
        prediction.checksum = "0" * 64  # type: ignore[misc]
    with pytest.raises(ValidationError):
        prediction.model_copy(update={"checksum": "0" * 64}).model_validate(
            prediction.model_copy(update={"checksum": "0" * 64})
        )


def test_request_accepts_only_runtime_contract_instances(phase8_context) -> None:
    request = InferenceRequest(
        feature_vector=phase8_context.feature_vector,
        group_id="left_lower_limb",
    )

    assert request.feature_vector is phase8_context.feature_vector
    with pytest.raises(ValidationError):
        InferenceRequest(
            feature_vector={"feature_vector_id": "not-a-runtime-contract"},
            group_id="left_lower_limb",
        )
