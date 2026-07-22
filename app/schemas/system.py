from pydantic import BaseModel, Field


class System(BaseModel):
    """
    Internal processing metadata.
    """

    validation_status: bool

    quality_score: float = Field(..., ge=0, le=100)

    processing_time_ms: float = Field(..., ge=0)

    source: str