"""Approval-aware, checksum-verifying Phase 7 production model loader."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pydantic import ValidationError

from app.config import production_model_config
from app.experiments.artifact_store import ExperimentArtifactStore
from app.models.production.contracts import (
    ProductionModelRegistration,
    ProductionModelSelection,
)
from app.models.production.serialization import (
    LoadedProductionModel,
    ProductionModelSerializer,
)

from .cache import InferenceModelCache
from .configuration import InferenceRuntimeConfig
from .contracts import ApprovedModelReferences
from .exceptions import (
    ModelApprovalError,
    ModelCompatibilityError,
    ModelIntegrityError,
    ModelLoadError,
)


@dataclass(frozen=True)
class LoadedInferenceModel:
    """Verified model plus pre-parsed schemas and immutable Phase 7 evidence."""

    predictor: LoadedProductionModel
    registration: ProductionModelRegistration
    selection: ProductionModelSelection
    feature_paths: tuple[tuple[str, str], ...]

    @property
    def feature_schema(self) -> tuple[str, ...]:
        """Return the exact ordered training feature schema."""

        return self.predictor.artifact.feature_schema

    @property
    def target_schema(self) -> tuple[str, ...]:
        """Return the exact ordered model output schema."""

        return self.predictor.artifact.target_schema


class ApprovedProductionModelLoader:
    """Load only Phase 7 models with verified affirmative selection evidence."""

    def __init__(
        self,
        artifact_store: ExperimentArtifactStore,
        *,
        config: InferenceRuntimeConfig | None = None,
        cache: InferenceModelCache[LoadedInferenceModel] | None = None,
    ) -> None:
        self._store = artifact_store
        self._config = config or InferenceRuntimeConfig()
        self._cache = cache or InferenceModelCache(
            self._config.model_cache_size
        )

    @property
    def cache(self) -> InferenceModelCache[LoadedInferenceModel]:
        """Expose cache state for operations and verification, never model mutation."""

        return self._cache

    def load(self, references: ApprovedModelReferences) -> LoadedInferenceModel:
        """Verify Phase 7 evidence and return a reusable immutable model."""

        cached = self._cache.get(references.cache_key)
        if cached is not None:
            return cached
        registration, selection = self._load_approval_evidence(references)
        self._validate_approval(registration, selection)
        loaded = self._load_model(registration)
        feature_paths = self._validate_compatibility(loaded, registration)
        candidate = LoadedInferenceModel(
            predictor=loaded,
            registration=registration,
            selection=selection,
            feature_paths=feature_paths,
        )
        return self._cache.put_if_absent(references.cache_key, candidate)

    def _load_approval_evidence(
        self,
        references: ApprovedModelReferences,
    ) -> tuple[ProductionModelRegistration, ProductionModelSelection]:
        try:
            self._store.verify(references.registration)
            self._store.verify(references.selection)
            registration = ProductionModelRegistration.model_validate(
                self._store.read_json(references.registration.relative_path)
            )
            selection = ProductionModelSelection.model_validate(
                self._store.read_json(references.selection.relative_path)
            )
        except ValidationError as exc:
            raise ModelLoadError("Phase 7 approval evidence is invalid.") from exc
        except Exception as exc:
            raise ModelIntegrityError(
                "Phase 7 approval evidence failed checksum verification."
            ) from exc
        return registration, selection

    @staticmethod
    def _validate_approval(
        registration: ProductionModelRegistration,
        selection: ProductionModelSelection,
    ) -> None:
        expected_selection_checksum = hashlib.sha256(
            json.dumps(
                {
                    "benchmark_experiment_ids": sorted(
                        selection.benchmark_experiment_ids
                    ),
                    "comparison_checksum": selection.comparison.checksum,
                    "production_experiment_id": selection.production_experiment_id,
                    "production_recommended": selection.production_recommended,
                    "rationale": selection.rationale,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if selection.checksum != expected_selection_checksum:
            raise ModelIntegrityError(
                "Phase 7 selection content checksum is invalid."
            )
        if (
            not selection.production_recommended
            or selection.production_experiment_id != registration.experiment_id
            or selection.comparison.recommended_experiment_id
            != registration.experiment_id
            or registration.experiment_id
            not in selection.comparison.experiment_ids
        ):
            raise ModelApprovalError(
                "Phase 7 did not approve this production model for runtime inference."
            )

    def _load_model(
        self,
        registration: ProductionModelRegistration,
    ) -> LoadedProductionModel:
        reference = registration.model_artifact
        if (
            reference.artifact_type != "model_candidate"
            or reference.media_type
            != production_model_config.PRODUCTION_MODEL_MEDIA_TYPE
        ):
            raise ModelCompatibilityError(
                "Registered model artifact type or media type is unsupported."
            )
        try:
            self._store.verify(reference)
            payload = self._store.read_bytes(reference.relative_path)
            return ProductionModelSerializer.loads(
                payload,
                expected_sha256=reference.sha256,
            )
        except Exception as exc:
            raise ModelIntegrityError(
                "Registered production model failed checksum or serialization verification."
            ) from exc

    def _validate_compatibility(
        self,
        loaded: LoadedProductionModel,
        registration: ProductionModelRegistration,
    ) -> tuple[tuple[str, str], ...]:
        artifact = loaded.artifact
        if (
            artifact.schema_version not in self._config.supported_model_versions
            or artifact.model_version not in self._config.supported_model_versions
            or registration.model_version != artifact.model_version
            or registration.dataset_version
            not in self._config.supported_dataset_versions
        ):
            raise ModelCompatibilityError(
                "Production model or training dataset schema version is unsupported."
            )
        if (
            registration.model_id != artifact.model_id
            or registration.configuration_hash != artifact.configuration_hash
            or registration.model_artifact.sha256.lower()
            != hashlib.sha256(
                ProductionModelSerializer.dumps(artifact)
            ).hexdigest()
        ):
            raise ModelCompatibilityError(
                "Production registration does not match the loaded model."
            )
        feature_paths = tuple(
            self._parse_feature_name(name) for name in artifact.feature_schema
        )
        if any(
            not name.startswith("target__") or len(name.split("__", 1)[1]) == 0
            for name in artifact.target_schema
        ):
            raise ModelCompatibilityError(
                "Production target schema is not a Phase 3 target schema."
            )
        if (
            len(feature_paths) != len(artifact.feature_mean)
            or len(artifact.target_schema) != len(artifact.target_mean)
        ):
            raise ModelCompatibilityError(
                "Production model feature or target dimensions are incompatible."
            )
        return feature_paths

    @staticmethod
    def _parse_feature_name(name: str) -> tuple[str, str]:
        parts = name.split("__")
        if (
            len(parts) != 3
            or parts[0] != "feature"
            or parts[1] not in {"motion", "pressure"}
            or not parts[2]
        ):
            raise ModelCompatibilityError(
                "Production feature schema is not a leakage-safe Phase 3 schema."
            )
        return parts[1], parts[2]
