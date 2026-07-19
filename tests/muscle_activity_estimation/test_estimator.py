"""Unit tests for implementation-independent muscle activity estimation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.lookup_engine.entities import LookupResult, ScientificSourceContext
from app.muscle_activity_estimation.entities import MuscleEstimationOutput
from app.muscle_activity_estimation.estimator import MuscleActivityEstimator
from app.muscle_activity_estimation.exceptions import (
    MuscleEstimationInputError,
    MuscleEstimationModelExecutionError,
    MuscleEstimationOutputError,
)
from app.schemas.feature_vector import FeatureVector


class StubMuscleEstimationModel:
    """Provide deterministic model output without selecting a model technology."""

    def estimate(
        self,
        feature_vector: FeatureVector,
        lookup_result: LookupResult,
    ) -> MuscleEstimationOutput:
        """Return a valid, extensible model output contract."""

        return MuscleEstimationOutput(
            model_version="model-1.8",
            confidence=0.91,
            muscles={"left_quad": 32.5, "right_ham": 27.0},
            derived_metrics={"fatigue": 11.0, "co_activation": 0.3},
        )


class FailingMuscleEstimationModel:
    """Simulate an implementation failure for exception-boundary tests."""

    def estimate(
        self,
        feature_vector: FeatureVector,
        lookup_result: LookupResult,
    ) -> MuscleEstimationOutput:
        """Raise an implementation-specific failure."""

        raise RuntimeError("model unavailable")


class InvalidOutputMuscleEstimationModel:
    """Simulate a model that violates the injected contract."""

    def estimate(
        self,
        feature_vector: FeatureVector,
        lookup_result: LookupResult,
    ) -> MuscleEstimationOutput:
        """Return a value with the wrong declared contract."""

        return "invalid"  # type: ignore[return-value]


class MuscleActivityEstimatorTests(unittest.TestCase):
    """Verify orchestration preserves contracts and input ownership."""

    def test_returns_immutable_extensible_estimate_with_lookup_provenance(self) -> None:
        """Valid input produces an immutable estimate with Knowledge Base sources."""

        feature_vector = _feature_vector("feature-vector-001")
        lookup_result = _lookup_result("feature-vector-001")
        estimator = MuscleActivityEstimator(
            StubMuscleEstimationModel(),
            estimator_version="estimator-2.0",
        )

        estimate = estimator.estimate(feature_vector, lookup_result)

        self.assertEqual(estimate.feature_vector_id, "feature-vector-001")
        self.assertEqual(estimate.estimator_version, "estimator-2.0")
        self.assertEqual(estimate.model_version, "model-1.8")
        self.assertEqual(estimate.muscles["left_quad"], 32.5)
        self.assertEqual(estimate.derived_metrics["co_activation"], 0.3)
        self.assertEqual(
            estimate.provenance.scientific_source_ids,
            ("SRC-SPORT-WEARABLES-2020",),
        )
        self.assertEqual(feature_vector.metadata.feature_vector_id, "feature-vector-001")

    def test_rejects_mismatched_lookup_result(self) -> None:
        """The estimator fails before invoking a model for mismatched inputs."""

        estimator = MuscleActivityEstimator(
            StubMuscleEstimationModel(),
            estimator_version="estimator-2.0",
        )

        with self.assertRaises(MuscleEstimationInputError):
            estimator.estimate(
                _feature_vector("feature-vector-001"),
                _lookup_result("feature-vector-002"),
            )

    def test_wraps_model_execution_failure(self) -> None:
        """Implementation failures remain isolated behind a domain exception."""

        estimator = MuscleActivityEstimator(
            FailingMuscleEstimationModel(),
            estimator_version="estimator-2.0",
        )

        with self.assertRaises(MuscleEstimationModelExecutionError):
            estimator.estimate(
                _feature_vector("feature-vector-001"),
                _lookup_result("feature-vector-001"),
            )

    def test_rejects_model_returning_wrong_contract(self) -> None:
        """Injected implementations must return the declared output DTO."""

        estimator = MuscleActivityEstimator(
            InvalidOutputMuscleEstimationModel(),
            estimator_version="estimator-2.0",
        )

        with self.assertRaises(MuscleEstimationOutputError):
            estimator.estimate(
                _feature_vector("feature-vector-001"),
                _lookup_result("feature-vector-001"),
            )


def _feature_vector(feature_vector_id: str) -> FeatureVector:
    """Construct the upstream-valid shape consumed by estimator tests."""

    field_values = {
        "metadata": SimpleNamespace(feature_vector_id=feature_vector_id),
    }
    if hasattr(FeatureVector, "model_construct"):
        return FeatureVector.model_construct(**field_values)
    return FeatureVector.construct(**field_values)


def _lookup_result(feature_vector_id: str) -> LookupResult:
    """Construct immutable Lookup Engine output with existing source metadata."""

    return LookupResult(
        feature_vector_id=feature_vector_id,
        position_profile={
            "position_key": "forward",
            "display_name": "Forward",
            "movement_demands": ("sprinting",),
            "interpretation_note": "Context only.",
            "source_ids": ("SRC-SPORT-WEARABLES-2020",),
        },
        injury_profiles=(),
        metric_context=(),
        scientific_sources=(
            ScientificSourceContext(
                source_id="SRC-SPORT-WEARABLES-2020",
                title="Wearable evidence",
                publication_year=2020,
                publisher="Sensors",
                persistent_identifier="https://example.invalid/source",
                evidence_level="moderate",
                review_status="reference_verified",
            ),
        ),
        evidence=(),
        provenance=(),
    )
