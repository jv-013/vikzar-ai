"""Immutable local production model and selection registry."""

from __future__ import annotations

from app.experiments.artifact_store import ExperimentArtifactStore
from app.experiments.contracts import ArtifactReference, ExperimentResult

from .contracts import ProductionModelRegistration, ProductionModelSelection
from .exceptions import ProductionRegistryError


class ProductionModelRegistry:
    """Register production evidence by reference without duplicating Phase 5 history."""

    def __init__(self, artifact_store: ExperimentArtifactStore) -> None:
        self._store = artifact_store

    def register(
        self,
        result: ExperimentResult,
    ) -> tuple[ProductionModelRegistration, ArtifactReference]:
        """Persist an immutable production candidate registration."""

        model_reference = result.model_candidate.artifact_reference
        try:
            self._store.verify(model_reference)
        except Exception as exc:
            raise ProductionRegistryError(
                "Production model artifact cannot be verified."
            ) from exc
        registration = ProductionModelRegistration(
            registration_id=f"production-registration-{result.spec.experiment_id}",
            model_id=result.model_candidate.model_id,
            model_version=result.model_candidate.model_version,
            experiment_id=result.spec.experiment_id,
            configuration_hash=result.spec.configuration_hash,
            dataset_id=result.spec.dataset_id,
            dataset_version=result.spec.dataset_version,
            dataset_checksum=result.spec.dataset_checksum,
            model_artifact=model_reference,
            evaluation_report_id=result.evaluation_report.report_id,
            evaluation_checksum=result.evaluation_report.report_checksum,
            reproducibility_checksum=result.reproducibility_checksum,
        )
        reference = self._store.write_json(
            relative_path=(
                f"production_registry/{result.model_candidate.model_id}/"
                f"{result.model_candidate.model_version}/"
                f"{result.spec.experiment_id}.json"
            ),
            artifact_type="production_model_registration",
            payload=registration,
        )
        return registration, reference

    def register_selection(
        self,
        selection: ProductionModelSelection,
    ) -> ArtifactReference:
        """Persist an immutable benchmark comparison decision."""

        return self._store.write_json(
            relative_path=f"production_selections/{selection.selection_id}.json",
            artifact_type="production_model_selection",
            payload=selection,
        )
