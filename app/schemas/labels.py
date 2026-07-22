from typing import Optional

from pydantic import BaseModel, Field


class Labels(BaseModel):
    """
    Ground-truth labels used during model training.

    These labels are NOT available during live inference.
    """

    movement_risk: Optional[float] = Field(default=None, ge=0, le=100)

    contact_risk: Optional[float] = Field(default=None, ge=0, le=100)

    impact_severity: Optional[float] = Field(default=None, ge=0)

    gait_drift: Optional[float] = Field(default=None, ge=0)

    injury_label: Optional[int] = Field(default=None)

    fatigue_label: Optional[int] = Field(default=None)