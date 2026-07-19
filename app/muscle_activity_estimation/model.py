"""Abstract model dependency for muscle activity estimation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.lookup_engine.entities import LookupResult
from app.muscle_activity_estimation.entities import MuscleEstimationOutput
from app.validation import ValidatedRawFeatureVector


@runtime_checkable
class MuscleEstimationModel(Protocol):
    """Implementation-independent contract for muscle estimation models.

    Implementations may use any approved estimation technique. They must not
    mutate either input and must return a validated ``MuscleEstimationOutput``.
    """

    def estimate(
        self,
        feature_vector: ValidatedRawFeatureVector,
        lookup_result: LookupResult,
    ) -> MuscleEstimationOutput:
        """Estimate named muscle activity from validated pipeline inputs.

        Parameters:
            feature_vector: RawFeatureVector already accepted by Validation.
            lookup_result: Immutable contextual output for the same vector.

        Returns:
            Model-owned, named muscle and derived-metric estimates.

        Exceptions:
            Exception: Implementation-specific execution failures are surfaced
                to the orchestration layer and wrapped in a domain exception.
        """
