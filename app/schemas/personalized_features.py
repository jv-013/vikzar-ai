from pydantic import BaseModel


class PersonalizedFeatures(BaseModel):
    """
    Player-specific deviation features.
    """

    cadence_deviation: float

    stride_length_deviation: float

    movement_intensity_deviation: float

    ground_contact_time_deviation: float

    peak_load_deviation: float

    symmetry_deviation: float