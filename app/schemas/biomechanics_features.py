from pydantic import BaseModel


class BiomechanicsFeatures(BaseModel):
    """
    High-level biomechanical descriptors.
    """

    movement_efficiency: float

    landing_efficiency: float

    running_consistency: float

    load_balance: float

    explosiveness_score: float