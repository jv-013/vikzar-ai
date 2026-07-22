"""
CalibrationFunction: the strategy abstraction for converting one raw
channel value into a CalibratedChannel.

See docs/development/CALIBRATION_DESIGN.md and
docs/architecture/10_SYSTEM_DECISIONS.md.

Deliberately absent: FSR402CharacterizedCalibration. Vikzar does not yet
possess an experimentally validated force-conversion curve for the
Interlink FSR 402 sensors used in the V1 Smart Pod — the PCB electrical
characteristics, resistor-divider values, and ADC transfer function are
not yet finalized. Writing that class now, even as a stub, would imply
the science exists when it does not. Its absence is the honest
statement that it doesn't — it is the designated extension point for
when Vikzar characterizes its own hardware, at which point only
defaults.py needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .channel import CalibratedChannel
from .unit import PhysicalUnit


class CalibrationFunction(Protocol):
    """A deterministic strategy for calibrating one raw channel value."""

    def calibrate(self, raw_value: int) -> CalibratedChannel:
        """Convert one raw, device-native channel value into a CalibratedChannel."""
        ...


@dataclass(frozen=True)
class IMUCalibration:
    """
    Linear calibration for accelerometer/gyroscope channels.

    calibrated = raw_value * scale - offset, the standard IMU datasheet
    form (sensitivity scaling, then bias removal). Kept as a separate
    class from EMGCalibration for scientific clarity and independent
    future evolution, even though both are presently linear.
    """

    scale: float
    offset: float
    unit: PhysicalUnit

    def calibrate(self, raw_value: int) -> CalibratedChannel:
        return CalibratedChannel(value=raw_value * self.scale - self.offset, unit=self.unit)


@dataclass(frozen=True)
class EMGCalibration:
    """
    Linear calibration for EMG channels: raw ADC counts to voltage.

    calibrated = raw_value * scale - offset. This is hardware-level
    ADC-to-voltage conversion only, not %MVC normalization — the latter
    requires per-player context and belongs to AI/Personalized Features,
    not Calibration.
    """

    scale: float
    offset: float
    unit: PhysicalUnit

    def calibrate(self, raw_value: int) -> CalibratedChannel:
        return CalibratedChannel(value=raw_value * self.scale - self.offset, unit=self.unit)


@dataclass(frozen=True)
class FSR402DevelopmentCalibration:
    """
    Temporary development-only calibration for the Interlink FSR 402
    sensors used in the V1 Smart Pod.

    NOT a real force-conversion curve. Output is always tagged
    PhysicalUnit.DEVELOPMENT_PLACEHOLDER, never a real force unit —
    claiming Newtons here would fabricate precision that doesn't exist.
    Replace with FSR402CharacterizedCalibration once Vikzar
    experimentally characterizes its own hardware; nothing outside
    defaults.py needs to change when that happens.
    """

    scale: float
    offset: float

    def calibrate(self, raw_value: int) -> CalibratedChannel:
        return CalibratedChannel(
            value=raw_value * self.scale - self.offset,
            unit=PhysicalUnit.DEVELOPMENT_PLACEHOLDER,
        )
