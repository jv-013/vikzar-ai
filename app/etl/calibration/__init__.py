"""
Calibration package.

Stage 4 of the ETL pipeline. See docs/architecture/04_ETL_ARCHITECTURE.md
and docs/development/CALIBRATION_DESIGN.md.

CalibratedFrame is exported for use elsewhere within app/etl (e.g. the
future Filtering stage). It must never be imported outside app/etl.
"""

from .calibrator import Calibrator, CalibratedFrameConsumer
from .channel import CalibratedChannel
from .defaults import default_calibration_functions
from .frame import CalibratedFrame
from .function import CalibrationFunction, EMGCalibration, FSR402DevelopmentCalibration, IMUCalibration
from .reading import CalibratedReading
from .unit import PhysicalUnit

__all__ = [
    "Calibrator",
    "CalibratedFrameConsumer",
    "CalibratedFrame",
    "CalibratedReading",
    "CalibratedChannel",
    "PhysicalUnit",
    "CalibrationFunction",
    "IMUCalibration",
    "EMGCalibration",
    "FSR402DevelopmentCalibration",
    "default_calibration_functions",
]
