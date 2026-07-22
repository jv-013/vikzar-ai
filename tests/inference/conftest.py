"""Production-shaped Phase 3, Phase 7, and runtime fixtures for Phase 8 tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.experiments.artifact_store import ExperimentArtifactStore
from app.inference import ApprovedModelReferences, InferenceEngine
from app.models.production import ProductionModelConfig, ProductionModelRegistry
from app.models.production.contracts import ProductionModelSelection
from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.group_feature_set import GroupFeatureSet
from app.schemas.hardware_provenance import HardwareProvenance
from app.schemas.player import Player
from app.schemas.quality_info import BiomarkerQualityInfo, QualityStatusInfo
from app.schemas.raw_feature_vector import RawFeatureVector
from app.schemas.session import Session
from app.validation import ValidatedRawFeatureVector, validate_raw_feature_vector
from tests.production_models.helpers import make_phase_seven_context


@dataclass(frozen=True)
class PhaseEightContext:
    """One isolated immutable artifact store and approved inference input."""

    root: Path
    store: ExperimentArtifactStore
    references: ApprovedModelReferences
    unapproved_references: ApprovedModelReferences
    feature_vector: ValidatedRawFeatureVector

    def engine(self) -> InferenceEngine:
        """Return a newly loaded engine using the copied immutable evidence."""

        return InferenceEngine.from_artifacts(self.store, self.references)


@pytest.fixture(scope="session")
def phase8_source(tmp_path_factory) -> tuple[Path, ApprovedModelReferences, ApprovedModelReferences]:
    """Create Phase 7 model evidence once from the normal Phase 3 dataset path."""

    root = tmp_path_factory.mktemp("phase8-source")
    dataset, benchmarks, policy, trainer, store = make_phase_seven_context(root)
    outcome = trainer.run(
        experiment_id="phase8-production-model",
        dataset=dataset,
        config=ProductionModelConfig(
            hidden_layer_sizes=(8,),
            learning_rate=0.02,
            epochs=100,
            random_seed=307,
        ),
        benchmark_results=benchmarks,
        created_by="phase-eight-tests",
        gate_policy=policy,
    )
    original = ApprovedModelReferences(
        registration=outcome.registration_artifact,
        selection=outcome.selection_artifact,
    )

    # The Phase 7 test dataset intentionally lets linear regression win. This
    # creates a contract-valid affirmative selection artifact for loader tests
    # while preserving the actual unapproved artifact for rejection tests.
    comparison = outcome.selection.comparison.model_copy(
        update={"recommended_experiment_id": outcome.registration.experiment_id}
    )
    rationale = "Phase 7 selection approves the production candidate."
    selection_payload = {
        "benchmark_experiment_ids": sorted(
            outcome.selection.benchmark_experiment_ids
        ),
        "comparison_checksum": comparison.checksum,
        "production_experiment_id": outcome.registration.experiment_id,
        "production_recommended": True,
        "rationale": rationale,
    }
    checksum = hashlib.sha256(
        json.dumps(
            selection_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    approved_selection = ProductionModelSelection(
        selection_id=f"phase8-approved-selection-{checksum[:24]}",
        production_experiment_id=outcome.registration.experiment_id,
        benchmark_experiment_ids=outcome.selection.benchmark_experiment_ids,
        comparison=comparison,
        production_recommended=True,
        rationale=rationale,
        checksum=checksum,
    )
    approved_reference = ProductionModelRegistry(store).register_selection(
        approved_selection
    )
    approved = ApprovedModelReferences(
        registration=outcome.registration_artifact,
        selection=approved_reference,
    )
    return root, approved, original


@pytest.fixture
def phase8_context(
    tmp_path,
    phase8_source,
) -> PhaseEightContext:
    """Copy immutable evidence so failure-path mutations cannot affect other tests."""

    source_root, references, unapproved = phase8_source
    root = tmp_path / "artifacts"
    shutil.copytree(source_root, root)
    store = ExperimentArtifactStore(root)
    valid_quality = BiomarkerQualityInfo(
        status=QualityStatusInfo.VALID,
        flags=(),
        rationale="ETL feature validation accepted the value.",
    )
    feature_vector = validate_raw_feature_vector(
        RawFeatureVector(
            feature_vector_id="phase8-feature-vector-001",
            timestamp=datetime(2026, 7, 19, 14, tzinfo=timezone.utc),
            schema_version="1.0.0",
            source="vikzar_etl_v1",
            player=Player(
                player_id="phase8-player-001",
                age=24,
                sex="male",
                dominant_leg="right",
                position="midfielder",
            ),
            session=Session(session_id="phase8-session-001", drill="cutting"),
            hardware=HardwareProvenance(
                firmware_revision="fw-1.0.0",
                hardware_revision="hw-v1",
                protocol_version="1",
            ),
            groups={
                "left_lower_limb": GroupFeatureSet(
                    window_start=0.0,
                    window_end=1000.0,
                    motion=DomainBiomarkers(
                        biomarkers={
                            "mean_angular_velocity": 16.0,
                            "peak_resultant_acceleration": 4.0,
                        },
                        quality={
                            "mean_angular_velocity": valid_quality,
                            "peak_resultant_acceleration": valid_quality,
                        },
                    ),
                )
            },
        )
    )
    return PhaseEightContext(
        root=root,
        store=store,
        references=references,
        unapproved_references=unapproved,
        feature_vector=feature_vector,
    )
