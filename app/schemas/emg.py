from pydantic import BaseModel, Field


class EMG(BaseModel):
    """
    EMG feature schema.

    These features are extracted by the ETL from synchronized
    EMG signals collected during training sessions.
    They are NOT available during live gameplay.
    """

    # Global EMG Features
    mean_activation: float = Field(..., ge=0)
    peak_activation: float = Field(..., ge=0)
    rms_activation: float = Field(..., ge=0)
    activation_duration: float = Field(..., ge=0)
    fatigue_index: float = Field(..., ge=0)
    activation_variability: float = Field(..., ge=0)

    # Muscle-Specific Features
    left_quadriceps_mean: float = Field(..., ge=0)
    right_quadriceps_mean: float = Field(..., ge=0)

    left_hamstring_mean: float = Field(..., ge=0)
    right_hamstring_mean: float = Field(..., ge=0)

    # Biomechanical Ratios
    left_right_asymmetry: float = Field(..., ge=0)

    hamstring_quadriceps_ratio: float = Field(..., ge=0)

    # Future Features
    co_activation_index: float | None = Field(
        default=None,
        ge=0
    )

    activation_onset_timing: float | None = Field(
        default=None,
        ge=0
    )