from typing import Optional

from pydantic import BaseModel, Field


class IMU(BaseModel):
    """
    IMU feature schema.

    This model contains biomechanical features extracted by the ETL
    from a 1-second sliding window. These are NOT raw sensor values.
    """

    # Acceleration Features
    mean_acceleration: float = Field(..., ge=0)
    peak_acceleration: float = Field(..., ge=0)
    min_acceleration: float
    resultant_acceleration: float = Field(..., ge=0)
    rms_acceleration: float = Field(..., ge=0)
    acceleration_variance: float = Field(..., ge=0)
    acceleration_std: float = Field(..., ge=0)

    # Jerk Features
    mean_jerk: float
    peak_jerk: float

    # Angular Velocity Features
    mean_angular_velocity: float
    peak_angular_velocity: float = Field(..., ge=0)
    angular_velocity_variance: float = Field(..., ge=0)

    # Motion Features
    rotation_magnitude: float = Field(..., ge=0)
   

    # Future ETL Features
    estimated_cadence: Optional[float] = Field(
        default=None,
        ge=0
    )

    estimated_stride_frequency: Optional[float] = Field(
        default=None,
        ge=0
    )