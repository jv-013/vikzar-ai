"""
CalibratedChannel: one calibrated value paired with its physical unit.

See docs/development/CALIBRATION_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from .unit import PhysicalUnit


@dataclass(frozen=True)
class CalibratedChannel:
    """
    A single calibrated sensor channel value.

    Purpose
        Guarantee that a calibrated value is never separated from its
        physical unit as it flows downstream. A bare float cannot make
        this guarantee; a full per-quantity class hierarchy (e.g.
        distinct Acceleration/Voltage types) was considered and
        rejected as premature given no static type-checker is
        configured anywhere in this project yet — this wrapper gets
        most of the practical benefit at a fraction of the cost.

    Attributes
        value: The calibrated numeric value.
        unit: The physical unit value is expressed in. See PhysicalUnit.
    """

    value: float
    unit: PhysicalUnit
