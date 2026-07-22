"""Contract and configuration-identity tests for Phase 5."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.dataset_builder import DatasetSplit
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import ExperimentCreationMetadata, ExperimentSpec
from tests.experiments.helpers import make_experiment_dataset, make_spec


def test_experiment_id_is_independent_from_configuration_hash() -> None:
    dataset = make_experiment_dataset()

    first = make_spec(dataset, experiment_id="exp_20260719_001")
    second = make_spec(dataset, experiment_id="exp_20260719_002")

    assert first.experiment_id != second.experiment_id
    assert first.configuration_hash == second.configuration_hash


def test_configuration_change_changes_hash_but_notes_and_creator_do_not() -> None:
    dataset = make_experiment_dataset()
    first = make_spec(dataset)
    changed_seed = make_spec(dataset, experiment_id="exp-seed", seed=42)
    changed_metadata = ExperimentSpec.create(
        experiment_id="exp-metadata",
        dataset_id=first.dataset_id,
        dataset_version=first.dataset_version,
        dataset_checksum=first.dataset_checksum,
        feature_schema_version=first.feature_schema_version,
        target_schema_version=first.target_schema_version,
        evaluation_framework_version=first.evaluation_framework_version,
        evaluation_split=first.evaluation_split,
        algorithm_identifier=first.algorithm_identifier,
        hyperparameters=first.hyperparameters,
        random_seed=first.random_seed,
        notes="Different human note.",
        creation_metadata=ExperimentCreationMetadata(
            created_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
            created_by="another-user",
        ),
    )

    assert changed_seed.configuration_hash != first.configuration_hash
    assert changed_metadata.configuration_hash == first.configuration_hash


def test_contracts_are_immutable_and_reject_forged_configuration_hash() -> None:
    spec = make_spec(make_experiment_dataset())

    with pytest.raises(ValidationError):
        spec.experiment_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(
            spec.model_dump(mode="python") | {"configuration_hash": "0" * 64}
        )


def test_spec_rejects_training_as_the_held_out_evaluation_split() -> None:
    dataset = make_experiment_dataset()
    valid = make_spec(dataset)

    with pytest.raises(ValidationError):
        ExperimentSpec.create(
            experiment_id="exp-train-evaluation",
            dataset_id=valid.dataset_id,
            dataset_version=valid.dataset_version,
            dataset_checksum=valid.dataset_checksum,
            feature_schema_version=valid.feature_schema_version,
            target_schema_version=valid.target_schema_version,
            evaluation_framework_version=valid.evaluation_framework_version,
            evaluation_split=DatasetSplit.TRAIN,
            algorithm_identifier=valid.algorithm_identifier,
            hyperparameters=canonical_metadata({}),
            random_seed=1,
            creation_metadata=valid.creation_metadata,
        )
