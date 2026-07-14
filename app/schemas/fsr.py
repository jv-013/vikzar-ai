"""Force-sensitive resistor (FSR) sensor structures"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class FSRReading:
    timestamp: float
    values: List[float]


@dataclass
class FSR:
    readings: List[FSRReading] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)
