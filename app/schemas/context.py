from typing import Optional

from pydantic import BaseModel

from app.knowledge_base.entities import (
    InjuryProfile,
    PlayerProfile,
    PositionProfile,
)


class Context(BaseModel):
    """
    Context added by the Knowledge Base and Lookup Engine.
    """

    player_profile: Optional[PlayerProfile] = None

    position_profile: Optional[PositionProfile] = None

    injury_profile: Optional[InjuryProfile] = None

    biomechanical_recommendation: Optional[str] = None