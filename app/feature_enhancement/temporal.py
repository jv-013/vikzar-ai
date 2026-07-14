"""
Temporal feature computation.
"""

from statistics import mean, variance

from app.schemas.temporal_features import TemporalFeatures

from .history_buffer import HistoryBuffer


class TemporalFeatureGenerator:
    """
    Generates temporal features from
    recent FeatureVectors.
    """

    def __init__(self, history_buffer: HistoryBuffer):
        self.history = history_buffer

    def generate(self) -> TemporalFeatures:

        history = self.history.get_all()

        if len(history) < 2:

            return TemporalFeatures(
                cadence_trend=0.0,
                load_trend=0.0,
                fatigue_trend=0.0,
                acceleration_trend=0.0,
                moving_average_load=0.0,
                moving_variance_load=0.0,
            )

        cadence = [
            fv.derived.cadence
            for fv in history
        ]

        load = [
            fv.fsr.peak_load
            for fv in history
        ]

        fatigue = [
            fv.muscles.estimated_muscle_fatigue
            for fv in history
        ]

        acceleration = [
            fv.imu.acc_peak
            for fv in history
        ]

        return TemporalFeatures(

            cadence_trend=cadence[-1] - cadence[0],

            load_trend=load[-1] - load[0],

            fatigue_trend=fatigue[-1] - fatigue[0],

            acceleration_trend=acceleration[-1] - acceleration[0],

            moving_average_load=mean(load),

            moving_variance_load=(
                variance(load)
                if len(load) > 1
                else 0.0
            ),
        )