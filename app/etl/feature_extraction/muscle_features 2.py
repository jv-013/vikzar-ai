"""
MuscleFeatures: muscle-domain biomechanical biomarker computation.

See docs/development/FEATURE_EXTRACTION_DESIGN.md, Section 11
(Scientific Rationale), for the formula and rationale behind every
biomarker computed below.
"""

from __future__ import annotations

import math
from typing import Dict, List

from app.etl.windowing import Window

from .feature_module import DomainExtractionResult


class MuscleFeatures:
    """
    Computes muscle-activity biomarkers from a wearable-mounted EMG
    Band's channels (quadriceps, hamstring), always read from each
    frame's "emg" reading — a role that may be entirely absent for a
    window (Match Mode, or a fully timed-out group). Frames lacking an
    "emg" reading, or lacking one of the two channels, are silently
    skipped; if no frame in the window has any emg data, extract()
    returns an empty mapping, never a fabricated zero.

    Stateless: extract() is a pure function of its window argument.

    sample_count (Decision 029) reflects the count of frames that had
    an "emg" reading present at all — not a separate per-channel
    (quadriceps vs. hamstring) count. A deliberate per-domain (not
    per-feature) simplification; see FEATURE_VALIDATION_DESIGN.md.
    """

    def extract(self, window: Window) -> DomainExtractionResult:
        quadriceps_values: List[float] = []
        hamstring_values: List[float] = []
        emg_frame_count = 0

        for frame in window.frames:
            reading = frame.readings.get("emg")
            if reading is None:
                continue
            emg_frame_count += 1
            channels = reading.filtered_channels
            if "quadriceps" in channels:
                quadriceps_values.append(channels["quadriceps"].value)
            if "hamstring" in channels:
                hamstring_values.append(channels["hamstring"].value)

        features: Dict[str, float] = {}

        if quadriceps_values:
            features["quadriceps_rms"] = math.sqrt(
                sum(v * v for v in quadriceps_values) / len(quadriceps_values)
            )
            features["quadriceps_mean_absolute_value"] = sum(
                abs(v) for v in quadriceps_values
            ) / len(quadriceps_values)

        if hamstring_values:
            features["hamstring_rms"] = math.sqrt(
                sum(v * v for v in hamstring_values) / len(hamstring_values)
            )
            features["hamstring_mean_absolute_value"] = sum(
                abs(v) for v in hamstring_values
            ) / len(hamstring_values)

        return DomainExtractionResult(
            features=features, sample_count=emg_frame_count if features else 0
        )
