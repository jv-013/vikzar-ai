"""Immutable contracts for muscle activity estimation output."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, Field, validator


class FrozenMetricMap(Mapping[str, float]):
    """An immutable, validated mapping of named numeric estimation metrics.

    Parameters:
        values: Metric names mapped to finite numeric values.

    Returns:
        A read-only mapping that owns a copy of the supplied values.

    Exceptions:
        TypeError: Raised when values is not a mapping or contains invalid keys
            or values.
    """

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, float]) -> None:
        """Validate values and store an immutable defensive copy.

        Parameters:
            values: Metric names mapped to finite numeric values.

        Returns:
            None.

        Exceptions:
            TypeError: Raised when the supplied metrics are invalid.
        """

        if not isinstance(values, Mapping):
            raise TypeError("Estimated metrics must be provided as a mapping.")

        copied_values: dict[str, float] = {}
        for name, value in values.items():
            if not isinstance(name, str) or not name.strip():
                raise TypeError("Estimated metric names must be non-empty strings.")
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError("Estimated metric values must be numeric.")
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise TypeError("Estimated metric values must be finite.")
            copied_values[name] = numeric_value

        self._values = MappingProxyType(copied_values)

    def __getitem__(self, key: str) -> float:
        """Return the value associated with one metric name."""

        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over metric names in their model-provided order."""

        return iter(self._values)

    def __len__(self) -> int:
        """Return the number of metrics in the mapping."""

        return len(self._values)

    def __repr__(self) -> str:
        """Return a diagnostic representation without exposing mutability."""

        return f"FrozenMetricMap({dict(self._values)!r})"

    def to_dict(self) -> dict[str, float]:
        """Return a mutable copy suitable for explicit serialization.

        Parameters:
            None.

        Returns:
            A new dictionary containing the metric values.

        Exceptions:
            None.
        """

        return dict(self._values)


class ImmutableMuscleEstimationModel(BaseModel):
    """Base Pydantic model for immutable estimation DTOs."""

    class Config:
        """Pydantic configuration compatible with supported versions."""

        arbitrary_types_allowed = True
        extra = "forbid"
        frozen = True


class MuscleEstimationOutput(BaseModel):
    """Model-owned output consumed by ``MuscleActivityEstimator``.

    The model implementation supplies named muscle activations and any named
    derived metrics. The estimator intentionally assigns no clinical meaning
    to the names or numeric values.
    """

    model_version: str
    confidence: float = Field(..., ge=0, le=1)
    muscles: Mapping[str, float]
    derived_metrics: Mapping[str, float] = Field(default_factory=dict)

    @validator("model_version")
    def validate_model_version(cls, value: str) -> str:
        """Reject blank model versions from injected implementations."""

        if not value.strip():
            raise ValueError("model_version must be a non-empty string.")
        return value

    @validator("muscles", "derived_metrics")
    def validate_metric_values(
        cls,
        value: Mapping[str, float],
    ) -> Mapping[str, float]:
        """Validate named metrics without imposing scientific thresholds."""

        FrozenMetricMap(value)
        return value


class EstimationProvenance(ImmutableMuscleEstimationModel):
    """Trace the immutable inputs and Knowledge Base evidence for an estimate."""

    feature_vector_id: str
    lookup_result_feature_vector_id: str
    scientific_source_ids: tuple[str, ...]


class MuscleActivityEstimate(ImmutableMuscleEstimationModel):
    """Immutable muscle-activity estimate passed to feature enhancement.

    Named values remain extensible through read-only metric mappings, allowing
    future estimators to support new muscles and derived metrics without
    changing this public contract.
    """

    feature_vector_id: str
    estimator_version: str
    model_version: str
    confidence: float = Field(..., ge=0, le=1)
    muscles: FrozenMetricMap
    derived_metrics: FrozenMetricMap
    provenance: EstimationProvenance

    @validator("feature_vector_id", "estimator_version", "model_version")
    def validate_required_identifier(cls, value: str) -> str:
        """Reject blank identifiers needed for auditable output."""

        if not value.strip():
            raise ValueError("Estimation identifiers must be non-empty strings.")
        return value

    @validator("muscles", "derived_metrics", pre=True)
    def freeze_metric_values(cls, value: Any) -> FrozenMetricMap:
        """Convert model-provided mappings into immutable public mappings."""

        if isinstance(value, FrozenMetricMap):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("Estimated metrics must be provided as a mapping.")
        return FrozenMetricMap(value)
