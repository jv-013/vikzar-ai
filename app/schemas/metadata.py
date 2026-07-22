from datetime import datetime
from pydantic import BaseModel, Field


class Metadata(BaseModel):
    """
    Metadata describing a single feature vector.
    """

    feature_vector_id: str

    timestamp: datetime

    schema_version: str = "1.0.0"

    window_start: datetime

    window_end: datetime

    sampling_rate_hz: int = Field(..., gt=0)

    window_size_ms: int = Field(..., gt=0)

    window_overlap_percent: float = Field(..., ge=0, le=100)