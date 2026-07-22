"""Unit tests for knowledge-base scientific provenance contracts."""

import unittest

from pydantic import ValidationError

from app.knowledge_base.entities import MetricProvenance


class MetricProvenanceTests(unittest.TestCase):
    """Verify metrics cannot enter the knowledge base without traceability."""

    def test_rejects_hardware_metric_without_sensor_source(self) -> None:
        """Hardware-measured metrics must name their measuring hardware."""

        with self.assertRaises(ValidationError):
            MetricProvenance(
                category="hardware_measured",
                scientific_basis="A sensor observes this signal.",
            )

    def test_rejects_ai_metric_without_measurable_inputs(self) -> None:
        """AI estimates must be traceable to measurable source features."""

        with self.assertRaises(ValidationError):
            MetricProvenance(
                category="ai_estimated",
                hardware_sources=("imu",),
                scientific_basis="A model estimates the value.",
            )

    def test_knowledge_entity_is_immutable(self) -> None:
        """Runtime callers cannot mutate validated scientific provenance."""

        provenance = MetricProvenance(
            category="hardware_measured",
            hardware_sources=("imu",),
            measurable_feature_paths=("raw_imu.linear_acceleration",),
            scientific_basis="An IMU accelerometer directly measures acceleration.",
        )

        with self.assertRaises((TypeError, ValidationError)):
            provenance.category = "ai_estimated"  # type: ignore[misc]
