from pydantic import BaseModel


class TemporalFeatures(BaseModel):
    """
    Features computed from recent history.
    """

    cadence_trend: float

    load_trend: float

    fatigue_trend: float

    acceleration_trend: float

    moving_average_load: float

    moving_variance_load: float