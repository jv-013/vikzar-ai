from pydantic import BaseModel, Field


class FSR(BaseModel):
    """
    Force Sensitive Resistor (FSR) feature schema.

    These biomechanical features are extracted by the ETL
    from a 1-second sliding window. These are NOT raw FSR
    sensor values.
    """

    # Load Features
    mean_load: float = Field(..., ge=0)
    peak_load: float = Field(..., ge=0)
    min_load: float = Field(..., ge=0)

    # Force Features
    total_impulse: float = Field(..., ge=0)
    ground_contact_time: float = Field(..., ge=0)

    # Loading Characteristics
    loading_rate: float = Field(..., ge=0)
    unloading_rate: float = Field(..., ge=0)

    # Pressure Distribution
    heel_load_percentage: float = Field(..., ge=0, le=100)
    midfoot_load_percentage: float = Field(..., ge=0, le=100)
    forefoot_load_percentage: float = Field(..., ge=0, le=100)

    # Future Expansion
    left_right_loading_symmetry: float | None = Field(
        default=None,
        ge=0,
        le=100
    )