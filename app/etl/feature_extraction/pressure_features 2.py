"""
PressureFeatures: pressure-domain biomechanical biomarker computation.

See docs/development/FEATURE_EXTRACTION_DESIGN.md, Section 11
(Scientific Rationale), for the formula and rationale behind every
biomarker computed below.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from app.etl.windowing import Window

from .feature_module import DomainExtractionResult

_FSR_CHANNEL_NAMES: Tuple[str, ...] = ("fsr_1", "fsr_2", "fsr_3")


class PressureFeatures:
    """
    Computes pressure biomarkers from a wearable-mounted Smart Pod's FSR
    channels (fsr_1/2/3), always read from each frame's
    "primary_motion" reading. Channels are summed into one total-load
    value per frame — combining a single device's own channels, not a
    cross-group collapse (Decision 022 only forbids merging across
    synchronization groups).

    Stateless: extract() is a pure function of its window argument.

    "loading_rate" is the maximum positive rate of change of total
    load within the window — deliberately not tied to a
    contact-onset definition, which would require an FSR threshold
    this project does not yet have validated data for (the same
    category of gap as FSR402's force-conversion curve;
    contact_duration is deferred for the same reason).

    "impulse" (trapezoidal integration of total load over elapsed
    time) inherits FSR402DevelopmentCalibration's existing
    DEVELOPMENT_PLACEHOLDER unit caveat — the operation itself needs no
    new assumption, but its output is only as physically meaningful as
    the load values it integrates.

    sample_count (Decision 029) reflects the total-load series length —
    the series every biomarker in this domain is drawn from.
    """

    def extract(self, window: Window) -> DomainExtractionResult:
        load_series: List[Tuple[float, float]] = []

        for frame in window.frames:
            reading = frame.readings.get("primary_motion")
            if reading is None:
                continue
            channels = reading.filtered_channels
            present = [name for name in _FSR_CHANNEL_NAMES if name in channels]
            if not present:
                continue
            total_load = sum(channels[name].value for name in present)
            load_series.append((frame.reference_timestamp, total_load))

        features: Dict[str, float] = {}

        if load_series:
            values = [value for _, value in load_series]
            features["peak_load"] = max(values)
            features["mean_load"] = sum(values) / len(values)
            features["rms_load"] = math.sqrt(sum(v * v for v in values) / len(values))

        if len(load_series) >= 2:
            rates = []
            impulse = 0.0
            for (t0, v0), (t1, v1) in zip(load_series, load_series[1:]):
                dt_seconds = (t1 - t0) / 1000.0
                if dt_seconds > 0:
                    rates.append((v1 - v0) / dt_seconds)
                    impulse += (v0 + v1) / 2.0 * dt_seconds
            if rates:
                features["loading_rate"] = max(rates)
            features["impulse"] = impulse

        return DomainExtractionResult(features=features, sample_count=len(load_series))
