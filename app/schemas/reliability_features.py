from pydantic import BaseModel


class ReliabilityFeatures(BaseModel):
    """
    Data quality indicators.
    """

    signal_quality: float

    feature_completeness: float

    packet_stability: float

    confidence_score: float