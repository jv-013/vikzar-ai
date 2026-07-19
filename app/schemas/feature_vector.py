"""Deprecated pre-V1 ETL-to-AI contract retained for source compatibility."""

from pydantic import BaseModel

from .metadata import Metadata
from .player import Player
from .session import Session

from .imu import IMU
from .fsr import FSR
from .emg import EMG
from .muscles import Muscles
from .derived import Derived
from .symmetry import Symmetry

from .context import Context
from .labels import Labels
from .system import System


class FeatureVector(BaseModel):
    """
    Deprecated legacy contract.

    RawFeatureVector is the locked, ETL-owned input to the AI pipeline.
    New runtime code must import and consume RawFeatureVector instead.
    """

    __deprecated__ = "Use app.schemas.raw_feature_vector.RawFeatureVector."

    metadata: Metadata

    player: Player

    session: Session

    imu: IMU

    fsr: FSR

    emg: EMG

    muscles: Muscles

    derived: Derived

    symmetry: Symmetry

    context: Context

    labels: Labels

    system: System
