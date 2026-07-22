from pydantic import BaseModel, Field


class Muscles(BaseModel):
    """
    AI-estimated muscle state.

    These values are estimated during inference from shin-pad
    biomechanical features. They are not directly measured
    during live gameplay.
    """

    # Estimated muscle activation (0–100%)
    left_quadriceps_activation: float = Field(..., ge=0, le=100)
    right_quadriceps_activation: float = Field(..., ge=0, le=100)

    left_hamstring_activation: float = Field(..., ge=0, le=100)
    right_hamstring_activation: float = Field(..., ge=0, le=100)

    # AI-derived metrics
    hamstring_quadriceps_ratio: float = Field(..., ge=0)

    left_right_activation_asymmetry: float = Field(..., ge=0)

    estimated_muscle_fatigue: float = Field(..., ge=0, le=100)

    confidence_score: float = Field(..., ge=0, le=1)