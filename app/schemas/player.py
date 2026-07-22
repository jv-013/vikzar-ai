from typing import Optional
from pydantic import BaseModel


class Player(BaseModel):

    player_id: str

    age: int

    sex: str

    height_cm: Optional[float] = None

    weight_kg: Optional[float] = None

    bmi: Optional[float] = None

    dominant_leg: str

    position: str

    fitness_level: Optional[str] = None

    injury_history: Optional[str] = None

    injury_status: Optional[str] = None