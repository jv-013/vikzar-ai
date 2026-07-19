"""Unit tests for immutable muscle activity estimation contracts."""

import math
import unittest

from pydantic import ValidationError

from app.muscle_activity_estimation.entities import (
    EstimationProvenance,
    FrozenMetricMap,
    MuscleActivityEstimate,
    MuscleEstimationOutput,
)


class MuscleEstimationEntityTests(unittest.TestCase):
    """Verify extensible metric maps and immutable estimation output."""

    def test_public_estimate_uses_immutable_metric_mappings(self) -> None:
        """Consumers cannot change named muscle or derived metric values."""

        estimate = MuscleActivityEstimate(
            feature_vector_id="feature-vector-001",
            estimator_version="estimator-2.0",
            model_version="model-1.8",
            confidence=0.9,
            muscles={"left_quad": 32.5, "right_ham": 27.0},
            derived_metrics={"fatigue": 11.0},
            provenance=EstimationProvenance(
                feature_vector_id="feature-vector-001",
                lookup_result_feature_vector_id="feature-vector-001",
                scientific_source_ids=("SRC-SPORT-WEARABLES-2020",),
            ),
        )

        with self.assertRaises(TypeError):
            estimate.muscles["left_quad"] = 90.0  # type: ignore[index]
        with self.assertRaises((TypeError, ValidationError)):
            estimate.model_version = "different-model"  # type: ignore[misc]

    def test_metric_map_defensively_copies_source_values(self) -> None:
        """Later mutations to a model-owned dictionary cannot affect output."""

        source_values = {"left_quad": 30.0}
        metrics = FrozenMetricMap(source_values)
        source_values["left_quad"] = 99.0

        self.assertEqual(metrics["left_quad"], 30.0)

    def test_model_output_rejects_non_finite_named_metrics(self) -> None:
        """Model output must contain finite values before orchestration."""

        with self.assertRaises((TypeError, ValidationError)):
            MuscleEstimationOutput(
                model_version="model-1.8",
                confidence=0.9,
                muscles={"left_quad": math.nan},
            )
