"""Phase 3-backed synthetic evidence factories for evaluation tests."""

from __future__ import annotations

import hashlib
import json

from app.dataset_builder import DatasetBuildSpec, DatasetBuilder, DatasetSplitPolicy
from app.dataset_builder.builder import DatasetBuildResult
from app.evaluation import GroundTruthRow, PredictionProvenance, PredictionRow, PredictionSet

from tests.dataset_builder.helpers import make_verified_session


def make_dataset_result() -> DatasetBuildResult:
    """Build ordinary synthetic Phase 3 output with varying direct EMG labels."""

    sessions = []
    for index, (quadriceps, hamstring) in enumerate(((0.2, 0.1), (0.4, 0.3), (0.6, 0.5)), start=1):
        session = make_verified_session(
            capture_session_id=f"evaluation-capture-{index}",
            player_id=f"player-{index}",
            session_id=f"evaluation-session-{index}",
        )
        labels = tuple(
            label.model_copy(
                update={"value": quadriceps if label.metric_name == "quadriceps_rms" else hamstring}
            )
            for label in session.labels
        )
        sessions.append(session.model_copy(update={"labels": labels}))
    return DatasetBuilder().build(
        sessions,
        DatasetBuildSpec(
            dataset_name="evaluation-synthetic-phase-three",
            target_metric_names=("quadriceps_rms", "hamstring_rms"),
            split_policy=DatasetSplitPolicy(train_fraction=1.0, validation_fraction=0.0, test_fraction=0.0),
        ),
    )


def make_prediction_set(
    result: DatasetBuildResult,
    *,
    offset: float = 0.0,
    omit_first_prediction: bool = False,
    empty: bool = False,
) -> PredictionSet:
    """Submit algorithm-neutral prediction rows against normal Phase 3 targets."""

    manifest_payload = result.dataset.model_dump(mode="json")
    manifest_hash = hashlib.sha256(
        (json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    ).hexdigest()
    provenance = PredictionProvenance(
        dataset_schema_version=result.dataset.schema_version,
        dataset_manifest_sha256=manifest_hash,
        dataset_created_at=result.dataset.created_at,
        feature_schema_names=result.dataset.feature_schema.feature_names,
        target_names=result.dataset.feature_schema.target_names,
    )
    if empty:
        return PredictionSet(
            model_id="test-model",
            model_version="1.0.0",
            dataset_id=result.dataset.dataset_id,
            split_id=result.examples[0].split,
            provenance=provenance,
        )
    truth_rows = tuple(
        GroundTruthRow(
            example_id=example.example_id,
            target_name=target.name,
            value=target.value,
            player_id=example.player_id,
            session_id=example.session_id,
            dataset_split=example.split,
        )
        for example in result.examples
        for target in example.targets
    )
    prediction_rows = tuple(
        PredictionRow(
            example_id=row.example_id,
            target_name=row.target_name,
            value=row.value + offset,
            confidence=0.9,
        )
        for index, row in enumerate(truth_rows)
        if not (omit_first_prediction and index == 0)
    )
    return PredictionSet(
        model_id="test-model",
        model_version="1.0.0",
        dataset_id=result.dataset.dataset_id,
        split_id=result.examples[0].split,
        prediction_rows=prediction_rows,
        ground_truth_rows=truth_rows,
        provenance=provenance,
    )
