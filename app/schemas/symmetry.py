from pydantic import BaseModel, Field


class Symmetry(BaseModel):
    """
    Left-right biomechanical symmetry metrics.

    These features quantify movement asymmetries that are
    associated with injury risk, fatigue, and performance.
    """

    # Muscle Symmetry
    quadriceps_symmetry: float = Field(..., ge=0, le=100)
    hamstring_symmetry: float = Field(..., ge=0, le=100)

    # Loading Symmetry
    loading_symmetry: float = Field(..., ge=0, le=100)

    # Movement Symmetry
    stride_symmetry: float = Field(..., ge=0, le=100)

    stance_time_symmetry: float = Field(..., ge=0, le=100)

    swing_time_symmetry: float = Field(..., ge=0, le=100)

    # Overall
    overall_symmetry_score: float = Field(..., ge=0, le=100)