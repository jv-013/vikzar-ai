"""Failure-path tests for runtime inputs and model outputs."""

from __future__ import annotations

import numpy as np
import pytest

from app.inference import InferenceRequest, InferenceRuntimeConfig
from app.inference.exceptions import InferenceInputError, InferenceOutputError
from app.inference.inference_engine import InferenceEngine
from app.inference.validation import InferenceOutputValidator
from app.schemas.quality_info import BiomarkerQualityInfo, QualityStatusInfo


def test_missing_model_feature_is_rejected(phase8_context) -> None:
    group = phase8_context.feature_vector.groups["left_lower_limb"]
    motion = group.motion
    assert motion is not None
    reduced_motion = motion.model_copy(
        update={
            "biomarkers": {"peak_resultant_acceleration": 4.0},
            "quality": {
                "peak_resultant_acceleration": motion.quality[
                    "peak_resultant_acceleration"
                ]
            },
        }
    )
    vector = phase8_context.feature_vector.model_copy(
        update={
            "groups": {
                "left_lower_limb": group.model_copy(
                    update={"motion": reduced_motion}
                )
            }
        }
    )

    with pytest.raises(InferenceInputError):
        phase8_context.engine().predict(vector)


def test_rejected_quality_feature_is_rejected(phase8_context) -> None:
    group = phase8_context.feature_vector.groups["left_lower_limb"]
    motion = group.motion
    assert motion is not None
    rejected = BiomarkerQualityInfo(
        status=QualityStatusInfo.REJECTED,
        flags=(),
        rationale="ETL rejected the value.",
    )
    updated_motion = motion.model_copy(
        update={
            "quality": {
                **motion.quality,
                "mean_angular_velocity": rejected,
            }
        }
    )
    vector = phase8_context.feature_vector.model_copy(
        update={
            "groups": {
                "left_lower_limb": group.model_copy(
                    update={"motion": updated_motion}
                )
            }
        }
    )

    with pytest.raises(InferenceInputError):
        phase8_context.engine().predict(vector)


def test_wrong_group_and_unsupported_input_version_are_rejected(
    phase8_context,
) -> None:
    engine = phase8_context.engine()
    with pytest.raises(InferenceInputError):
        engine.predict(
            phase8_context.feature_vector,
            group_id="right_lower_limb",
        )

    unsupported = phase8_context.feature_vector.model_copy(
        update={"schema_version": "9.9.9"}
    )
    with pytest.raises(InferenceInputError):
        engine.predict(unsupported)


def test_empty_and_oversized_batches_are_rejected(phase8_context) -> None:
    engine = phase8_context.engine()
    with pytest.raises(InferenceInputError):
        engine.predict_batch(())

    config = InferenceRuntimeConfig(max_batch_size=1)
    limited = InferenceEngine(
        phase8_context.store,
        phase8_context.references,
        config=config,
    )
    request = InferenceRequest(
        feature_vector=phase8_context.feature_vector,
        group_id="left_lower_limb",
    )
    with pytest.raises(InferenceInputError):
        limited.predict_batch((request, request))


@pytest.mark.parametrize(
    "output",
    (
        np.asarray([[1.0]]),
        np.asarray([[1.0, float("nan")]]),
    ),
)
def test_invalid_model_output_is_rejected(output) -> None:
    with pytest.raises(InferenceOutputError):
        InferenceOutputValidator.validate(
            output,
            row_count=1,
            target_count=2,
        )
