"""Single, batch, reproducibility, and regression tests for Phase 8."""

from __future__ import annotations

from app.inference import InferenceRequest


def test_single_prediction_contains_only_model_outputs_and_lineage(
    phase8_context,
) -> None:
    prediction = phase8_context.engine().predict(phase8_context.feature_vector)

    assert tuple(value.target_name for value in prediction.predictions) == (
        "target__quadriceps_rms",
        "target__hamstring_rms",
    )
    assert prediction.metadata.source_feature_vector_id == (
        phase8_context.feature_vector.feature_vector_id
    )
    assert prediction.metadata.group_id == "left_lower_limb"
    dumped = prediction.model_dump(mode="json")
    assert not {
        "risk_score",
        "risk_category",
        "recommendation",
        "fatigue",
        "alert",
    }.intersection(dumped)


def test_identical_model_input_and_configuration_are_byte_reproducible(
    phase8_context,
) -> None:
    first = phase8_context.engine().predict(phase8_context.feature_vector)
    second = phase8_context.engine().predict(phase8_context.feature_vector)

    assert first.model_dump_json() == second.model_dump_json()
    assert first.prediction_id == second.prediction_id
    assert first.checksum == second.checksum


def test_batch_prediction_preserves_order_and_matches_single_prediction(
    phase8_context,
) -> None:
    first_vector = phase8_context.feature_vector
    second_vector = first_vector.model_copy(
        update={"feature_vector_id": "phase8-feature-vector-002"}
    )
    requests = (
        InferenceRequest(
            feature_vector=first_vector,
            group_id="left_lower_limb",
        ),
        InferenceRequest(
            feature_vector=second_vector,
            group_id="left_lower_limb",
        ),
    )
    engine = phase8_context.engine()

    batch = engine.predict_batch(requests)

    assert len(batch) == 2
    assert tuple(
        result.metadata.source_feature_vector_id for result in batch
    ) == (
        "phase8-feature-vector-001",
        "phase8-feature-vector-002",
    )
    assert batch[0] == engine.predict(first_vector)
    assert batch[0].predictions == batch[1].predictions


def test_extra_runtime_biomarkers_do_not_change_approved_feature_order(
    phase8_context,
) -> None:
    baseline = phase8_context.engine().predict(phase8_context.feature_vector)
    group = phase8_context.feature_vector.groups["left_lower_limb"]
    motion = group.motion
    assert motion is not None
    quality = next(iter(motion.quality.values()))
    expanded_motion = motion.model_copy(
        update={
            "biomarkers": {**motion.biomarkers, "unused_runtime_value": 9999.0},
            "quality": {**motion.quality, "unused_runtime_value": quality},
        }
    )
    expanded_group = group.model_copy(update={"motion": expanded_motion})
    expanded = phase8_context.feature_vector.model_copy(
        update={"groups": {"left_lower_limb": expanded_group}}
    )

    result = phase8_context.engine().predict(expanded)

    assert result.predictions == baseline.predictions
    assert result.metadata.feature_schema == (
        "feature__motion__mean_angular_velocity",
        "feature__motion__peak_resultant_acceleration",
    )
