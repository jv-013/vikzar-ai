from typing import Optional
from pydantic import BaseModel


class Session(BaseModel):
    """
    Information describing the current training or match session.
    """

    session_id: str

    drill: Optional[str] = None

    training_intensity: Optional[str] = None

    surface: Optional[str] = None

    footwear: Optional[str] = None

    weather: Optional[str] = None

    temperature_c: Optional[float] = None

    humidity_percent: Optional[float] = None

    fatigue_level: Optional[float] = None