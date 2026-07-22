"""Generation of direct, measured EMG labels from accepted ETL biomarkers."""

from __future__ import annotations

from app.schemas.domain_biomarkers import DomainBiomarkers

from .contracts.capture import EMGRecording
from .contracts.output import MeasuredEMGLabel


class MeasuredEMGLabelGenerator:
    """Create labels by copying accepted measured EMG values without estimation."""

    def generate(
        self,
        *,
        aligned_window_id: str,
        source_feature_vector_id: str,
        group_id: str,
        measurements: DomainBiomarkers,
        recording: EMGRecording,
    ) -> tuple[MeasuredEMGLabel, ...]:
        """Generate one direct-measurement label per muscle biomarker.

        Args:
            aligned_window_id: Verified output-window identifier.
            source_feature_vector_id: ETL feature-vector identifier.
            group_id: Limb synchronization-group identifier.
            measurements: ETL-derived EMG measurements from the capture.
            recording: Acquisition metadata defining measurement units.

        Returns:
            Immutable, measured EMG labels in deterministic metric-name order.
        """

        return tuple(
            MeasuredEMGLabel(
                aligned_window_id=aligned_window_id,
                group_id=group_id,
                metric_name=metric_name,
                value=value,
                amplitude_unit=recording.amplitude_unit,
                normalization_method=recording.normalization_method,
                source_feature_vector_id=source_feature_vector_id,
            )
            for metric_name, value in sorted(measurements.biomarkers.items())
        )
