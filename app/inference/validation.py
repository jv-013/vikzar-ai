"""Strict input and output validation for approved model inference."""

from __future__ import annotations

import math

import numpy as np

from app.schemas.quality_info import QualityStatusInfo
from app.validation.validator import RawFeatureVectorValidator

from .configuration import InferenceRuntimeConfig
from .contracts import InferenceRequest
from .exceptions import InferenceInputError, InferenceOutputError
from .model_loader import LoadedInferenceModel


class InferenceInputValidator:
    """Map trusted ETL biomarkers to the exact ordered Phase 3 feature schema."""

    def __init__(self, config: InferenceRuntimeConfig) -> None:
        self._config = config
        self._runtime_validator = RawFeatureVectorValidator()

    def matrix(
        self,
        requests: tuple[InferenceRequest, ...],
        model: LoadedInferenceModel,
    ) -> np.ndarray:
        """Return one finite matrix without engineering or imputing features."""

        if not requests:
            raise InferenceInputError("Inference batch must not be empty.")
        if len(requests) > self._config.max_batch_size:
            raise InferenceInputError("Inference batch exceeds configured capacity.")
        rows: list[list[float]] = []
        for request in requests:
            vector = request.feature_vector
            if vector.schema_version not in self._config.supported_input_versions:
                raise InferenceInputError(
                    "Validated feature vector schema version is unsupported."
                )
            report = self._runtime_validator.validate(vector)
            if not report.is_valid:
                raise InferenceInputError(
                    "Feature vector no longer satisfies the validated runtime contract."
                )
            group = vector.groups.get(request.group_id)
            if group is None:
                raise InferenceInputError(
                    f"Feature vector does not contain group '{request.group_id}'."
                )
            row: list[float] = []
            for domain_name, metric_name in model.feature_paths:
                domain = getattr(group, domain_name)
                if domain is None or metric_name not in domain.biomarkers:
                    raise InferenceInputError(
                        f"Required model feature is missing: "
                        f"feature__{domain_name}__{metric_name}."
                    )
                quality = domain.quality[metric_name]
                value = domain.biomarkers[metric_name]
                if quality.status is QualityStatusInfo.REJECTED:
                    raise InferenceInputError(
                        f"Required model feature was rejected by ETL quality control: "
                        f"feature__{domain_name}__{metric_name}."
                    )
                if not math.isfinite(value):
                    raise InferenceInputError(
                        f"Required model feature must be finite: "
                        f"feature__{domain_name}__{metric_name}."
                    )
                row.append(value)
            rows.append(row)
        return np.asarray(rows, dtype=np.float64)


class InferenceOutputValidator:
    """Reject output that disagrees with the approved target schema."""

    @staticmethod
    def validate(
        predictions: np.ndarray,
        *,
        row_count: int,
        target_count: int,
    ) -> np.ndarray:
        """Return a float64 view only when dimensions and values are valid."""

        matrix = np.asarray(predictions, dtype=np.float64)
        if matrix.shape != (row_count, target_count):
            raise InferenceOutputError(
                "Production model output dimensions do not match its target schema."
            )
        if not np.isfinite(matrix).all():
            raise InferenceOutputError(
                "Production model emitted a non-finite prediction."
            )
        return matrix
