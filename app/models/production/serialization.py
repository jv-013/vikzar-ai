"""Canonical production model serialization, verification, loading, and prediction."""

from __future__ import annotations

import hashlib
import json

import numpy as np
from pydantic import ValidationError

from .contracts import ProductionModelArtifact
from .exceptions import ProductionDataError, ProductionSerializationError


class LoadedProductionModel:
    """Validated immutable production model used only for offline verification."""

    def __init__(self, artifact: ProductionModelArtifact) -> None:
        self._artifact = artifact

    @property
    def artifact(self) -> ProductionModelArtifact:
        """Return the immutable loaded artifact."""

        return self._artifact

    def predict(self, features: np.ndarray) -> np.ndarray:
        """Produce deterministic multi-output regression predictions."""

        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != len(self._artifact.feature_schema):
            raise ProductionDataError("Production features do not match the artifact schema.")
        if not np.isfinite(matrix).all():
            raise ProductionDataError("Production features must be finite.")
        values = (
            matrix - np.asarray(self._artifact.feature_mean, dtype=np.float64)
        ) / np.asarray(self._artifact.feature_scale, dtype=np.float64)
        for index, layer in enumerate(self._artifact.layers):
            values = values @ np.asarray(layer.weights, dtype=np.float64) + np.asarray(
                layer.biases,
                dtype=np.float64,
            )
            if index < len(self._artifact.layers) - 1:
                values = np.tanh(values)
        return (
            values * np.asarray(self._artifact.target_scale, dtype=np.float64)
            + np.asarray(self._artifact.target_mean, dtype=np.float64)
        )


class ProductionModelSerializer:
    """Serialize production models as canonical JSON without executable pickle."""

    @staticmethod
    def dumps(artifact: ProductionModelArtifact) -> bytes:
        """Return deterministic UTF-8 artifact bytes."""

        return (
            json.dumps(
                artifact.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def loads(
        payload: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> LoadedProductionModel:
        """Verify checksum, schema, and canonical representation before loading."""

        if (
            expected_sha256 is not None
            and hashlib.sha256(payload).hexdigest() != expected_sha256.lower()
        ):
            raise ProductionSerializationError("Production model checksum failed.")
        try:
            artifact = ProductionModelArtifact.model_validate_json(payload)
        except (ValidationError, ValueError, UnicodeDecodeError) as exc:
            raise ProductionSerializationError("Production model artifact is invalid.") from exc
        if ProductionModelSerializer.dumps(artifact) != payload:
            raise ProductionSerializationError("Production artifact is not canonical JSON.")
        return LoadedProductionModel(artifact)
