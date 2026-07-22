"""Unit tests for immutable Lookup Engine public contracts."""

import unittest

from pydantic import ValidationError

from app.lookup_engine.entities import MetricProvenanceContext


class LookupEntityTests(unittest.TestCase):
    """Verify the Lookup Engine result contracts remain immutable and typed."""

    def test_provenance_context_is_immutable(self) -> None:
        """Public measurement provenance cannot be changed by a consumer."""

        context = MetricProvenanceContext(
            metric_name="imu.resultant_acceleration",
            category="mathematically_derived",
            measured_by=("imu",),
            measurable_feature_paths=("raw_imu.linear_acceleration",),
            scientific_basis="The vector magnitude is derived from tri-axial acceleration.",
        )

        with self.assertRaises((TypeError, ValidationError)):
            context.category = "ai_estimated"  # type: ignore[misc]
