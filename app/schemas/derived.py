from pydantic import BaseModel, Field


class Derived(BaseModel):
    """
    Derived biomechanical features extracted by the ETL.

    These features summarize movement mechanics over a
    sliding window and are independent of the underlying
    sensor hardware.
    """

    # Gait & Locomotion
    cadence: float = Field(..., ge=0)
    stride_frequency: float = Field(..., ge=0)
    stride_length: float = Field(..., ge=0)

    # Movement Mechanics
    movement_intensity: float = Field(..., ge=0)
    braking_force: float = Field(..., ge=0)
    propulsion_force: float = Field(..., ge=0)
    vertical_oscillation: float = Field(..., ge=0)

    # Temporal Characteristics
    stance_time: float = Field(..., ge=0)
    swing_time: float = Field(..., ge=0)
    flight_time: float = Field(..., ge=0)

    # Agility & Stability
    change_of_direction_angle: float = Field(..., ge=0, le=180)
    turning_rate: float = Field(..., ge=0)
    landing_stability: float = Field(..., ge=0)
    landing_force_distribution: float = Field(..., ge=0)

    # Performance Indicators
    gait_stability: float = Field(..., ge=0)
    movement_efficiency: float = Field(..., ge=0)

    # Load Monitoring
    cumulative_mechanical_load: float = Field(..., ge=0)