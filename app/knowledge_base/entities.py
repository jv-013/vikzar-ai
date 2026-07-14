"""
Knowledge Base entity definitions.
"""

from typing import List, Optional

from pydantic import BaseModel


class PlayerProfile(BaseModel):
    """
    Stores player profile knowledge.
    """

    level: str

    expected_running_intensity: str

    expected_sprint_frequency: str

    expected_jump_frequency: str


class PositionProfile(BaseModel):
    """
    Stores football position characteristics.
    """

    position: str

    movement_profile: str

    expected_workload: str

    sprint_frequency: str

    direction_changes: str


class InjuryProfile(BaseModel):
    """
    Stores injury-related knowledge.
    """

    injury_name: str

    risk_level: str

    affected_muscles: List[str]

    recovery_notes: Optional[str] = None


class BiomechanicsRule(BaseModel):
    """
    Stores biomechanics recommendations.
    """

    name: str

    recommendation: str