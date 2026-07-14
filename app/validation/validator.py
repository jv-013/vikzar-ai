"""
Main Validation Engine for Vikzar AI.
"""

from app.schemas.feature_vector import FeatureVector

from .report import ValidationReport
from .rules import (
    POSITIVE_NUMBER,
    PERCENTAGE,
    CONFIDENCE_SCORE,
    NON_EMPTY_STRING,
)


class FeatureVectorValidator:
    """
    Validates a FeatureVector before it enters the AI pipeline.
    """

    def validate(self, feature_vector: FeatureVector) -> ValidationReport:
        report = ValidationReport()

        self._validate_player(feature_vector, report)
        self._validate_imu(feature_vector, report)
        self._validate_fsr(feature_vector, report)
        self._validate_emg(feature_vector, report)
        self._validate_muscles(feature_vector, report)

        return report

    def _validate_player(
        self,
        feature_vector: FeatureVector,
        report: ValidationReport,
    ) -> None:

        player = feature_vector.player

        if not POSITIVE_NUMBER.validator(player.age):
            report.add_error("Player age must be positive.")

        if not NON_EMPTY_STRING.validator(player.player_id):
            report.add_error("Player ID cannot be empty.")

    def _validate_imu(
        self,
        feature_vector: FeatureVector,
        report: ValidationReport,
    ) -> None:

        imu = feature_vector.imu

        if not POSITIVE_NUMBER.validator(imu.peak_acceleration):
            report.add_error("Peak acceleration is invalid.")

    def _validate_fsr(
        self,
        feature_vector: FeatureVector,
        report: ValidationReport,
    ) -> None:

        fsr = feature_vector.fsr

        if not POSITIVE_NUMBER.validator(fsr.peak_load):
            report.add_error("Peak load is invalid.")

    def _validate_emg(
        self,
        feature_vector: FeatureVector,
        report: ValidationReport,
    ) -> None:

        emg = feature_vector.emg

        if not POSITIVE_NUMBER.validator(emg.peak_activation):
            report.add_error("Peak EMG activation is invalid.")

    def _validate_muscles(
        self,
        feature_vector: FeatureVector,
        report: ValidationReport,
    ) -> None:

        muscles = feature_vector.muscles

        if not CONFIDENCE_SCORE.validator(
            muscles.confidence_score
        ):
            report.add_error(
                "Muscle confidence score must be between 0 and 1."
            )

        if not PERCENTAGE.validator(
            muscles.estimated_muscle_fatigue
        ):
            report.add_error(
                "Estimated muscle fatigue must be between 0 and 100."
            )