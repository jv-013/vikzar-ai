"""Experiment, evaluation, registry, benchmark-selection, and reproduction tests."""

from __future__ import annotations

import pytest

from app.experiments.registry import ExperimentRegistry
from app.models.production import ProductionModelConfig
from app.models.production.exceptions import ProductionSelectionError
from app.models.production.selection import ProductionModelSelector
from tests.production_models.helpers import make_phase_seven_context


def _config() -> ProductionModelConfig:
    return ProductionModelConfig(
        hidden_layer_sizes=(8,),
        learning_rate=0.02,
        epochs=100,
        random_seed=307,
    )


def test_complete_production_lifecycle_registers_all_required_evidence(tmp_path) -> None:
    dataset, benchmarks, policy, trainer, store = make_phase_seven_context(tmp_path)

    outcome = trainer.run(
        experiment_id="production-model-001",
        dataset=dataset,
        config=_config(),
        benchmark_results=benchmarks,
        created_by="phase-seven-integration",
        gate_policy=policy,
    )

    result = outcome.experiment_result
    assert result.evaluation_report.provenance.dataset_id == dataset.dataset.dataset_id
    assert result.provenance.model_artifact_checksum == (
        outcome.registration.model_artifact.sha256
    )
    assert outcome.registration.configuration_hash == result.spec.configuration_hash
    assert len(outcome.selection.benchmark_experiment_ids) == 4
    assert outcome.selection.comparison.experiment_ids
    store.verify(outcome.registration_artifact)
    store.verify(outcome.selection_artifact)
    assert len(ExperimentRegistry(store).history("production-model-001")) == 2


def test_production_retraining_with_unique_ids_reproduces_scientific_checksums(
    tmp_path,
) -> None:
    dataset, benchmarks, policy, trainer, _ = make_phase_seven_context(tmp_path)

    first = trainer.run(
        experiment_id="production-repro-a",
        dataset=dataset,
        config=_config(),
        benchmark_results=benchmarks,
        created_by="phase-seven-reproduction",
        gate_policy=policy,
    ).experiment_result
    second = trainer.run(
        experiment_id="production-repro-b",
        dataset=dataset,
        config=_config(),
        benchmark_results=benchmarks,
        created_by="phase-seven-reproduction",
        gate_policy=policy,
    ).experiment_result

    assert first.spec.configuration_hash == second.spec.configuration_hash
    assert first.provenance.model_artifact_checksum == second.provenance.model_artifact_checksum
    assert first.provenance.evaluation_report_checksum == (
        second.provenance.evaluation_report_checksum
    )
    assert first.reproducibility_checksum == second.reproducibility_checksum


def test_selection_requires_every_permanent_benchmark(tmp_path) -> None:
    dataset, benchmarks, policy, trainer, _ = make_phase_seven_context(tmp_path)
    outcome = trainer.run(
        experiment_id="production-selection-source",
        dataset=dataset,
        config=_config(),
        benchmark_results=benchmarks,
        created_by="phase-seven-selection",
        gate_policy=policy,
    )

    with pytest.raises(ProductionSelectionError):
        ProductionModelSelector().select(
            outcome.experiment_result,
            benchmarks[:-1],
        )


def test_selection_is_exactly_the_phase_five_comparison_decision(tmp_path) -> None:
    dataset, benchmarks, policy, trainer, _ = make_phase_seven_context(tmp_path)
    outcome = trainer.run(
        experiment_id="production-comparison-authority",
        dataset=dataset,
        config=_config(),
        benchmark_results=benchmarks,
        created_by="phase-seven-selection",
        gate_policy=policy,
    )

    assert outcome.selection.production_recommended is (
        outcome.selection.comparison.recommended_experiment_id
        == outcome.experiment_result.spec.experiment_id
    )
