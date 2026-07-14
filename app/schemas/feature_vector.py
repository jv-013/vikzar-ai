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
    Final production Feature Vector.

    This is the official contract between
    the ETL subsystem and the AI subsystem.

    Every 100 ms, one FeatureVector enters
    the AI pipeline.
    """

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