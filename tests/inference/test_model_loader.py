"""Approval, integrity, compatibility, and cache tests for model loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.inference import ApprovedProductionModelLoader, InferenceRuntimeConfig
from app.inference.exceptions import (
    ModelApprovalError,
    ModelCompatibilityError,
    ModelIntegrityError,
)


def test_loader_accepts_only_approved_phase_seven_model(phase8_context) -> None:
    loader = ApprovedProductionModelLoader(phase8_context.store)

    loaded = loader.load(phase8_context.references)

    assert loaded.registration.model_id == loaded.predictor.artifact.model_id
    assert loaded.selection.production_recommended
    assert loaded.feature_paths == (
        ("motion", "mean_angular_velocity"),
        ("motion", "peak_resultant_acceleration"),
    )


def test_loader_rejects_unapproved_phase_seven_selection(phase8_context) -> None:
    with pytest.raises(ModelApprovalError):
        ApprovedProductionModelLoader(phase8_context.store).load(
            phase8_context.unapproved_references
        )


def test_loader_rejects_tampered_model_checksum(phase8_context) -> None:
    registration = phase8_context.store.read_json(
        phase8_context.references.registration.relative_path
    )
    model_path = phase8_context.root / Path(
        registration["model_artifact"]["relative_path"]
    )
    model_path.write_bytes(model_path.read_bytes() + b"tampered")

    with pytest.raises(ModelIntegrityError):
        ApprovedProductionModelLoader(phase8_context.store).load(
            phase8_context.references
        )


def test_loader_rejects_tampered_approval_evidence(phase8_context) -> None:
    selection_path = phase8_context.root / Path(
        phase8_context.references.selection.relative_path
    )
    selection_path.write_bytes(selection_path.read_bytes() + b"tampered")

    with pytest.raises(ModelIntegrityError):
        ApprovedProductionModelLoader(phase8_context.store).load(
            phase8_context.references
        )


def test_loader_rejects_unsupported_model_version(phase8_context) -> None:
    config = InferenceRuntimeConfig(supported_model_versions=("9.9.9",))

    with pytest.raises(ModelCompatibilityError):
        ApprovedProductionModelLoader(
            phase8_context.store,
            config=config,
        ).load(phase8_context.references)


def test_loader_rejects_unsupported_dataset_version(phase8_context) -> None:
    config = InferenceRuntimeConfig(supported_dataset_versions=("9.9.9",))

    with pytest.raises(ModelCompatibilityError):
        ApprovedProductionModelLoader(
            phase8_context.store,
            config=config,
        ).load(phase8_context.references)


def test_loader_reuses_cached_verified_model_without_reloading(
    phase8_context,
    monkeypatch,
) -> None:
    loader = ApprovedProductionModelLoader(phase8_context.store)
    first = loader.load(phase8_context.references)
    monkeypatch.setattr(
        phase8_context.store,
        "read_bytes",
        lambda *_: pytest.fail("cached model was read again"),
    )

    second = loader.load(phase8_context.references)

    assert second is first
    assert loader.cache.size == 1
