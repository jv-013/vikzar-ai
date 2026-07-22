"""
MotionFeatures: motion-domain biomechanical biomarker computation.

See docs/development/FEATURE_EXTRACTION_DESIGN.md, Section 11
(Scientific Rationale), for the formula and rationale behind every
biomarker computed below.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from app.etl.windowing import Window

from .feature_module import DomainExtractionResult


def _count_local_maxima(values: Sequence[float]) -> int:
    return sum(
        1
        for i in range(1, len(values) - 1)
        if values[i] > values[i - 1] and values[i] > values[i + 1]
    )


class MotionFeatures:
    """
    Computes motion biomarkers from a wearable-mounted Smart Pod's
    accelerometer and gyroscope channels (accel_x/y/z, gyro_x/y/z),
    always read from each frame's "primary_motion" reading — the one
    role every Window's frames are guaranteed to have.

    Stateless: extract() is a pure function of its window argument, no
    constructor state, one shared instance is safe across every
    synchronization group and every call.

    Cadence is a simple, documented, swappable V1 heuristic (counting
    local maxima in the resultant acceleration signal), not a
    scientifically validated gait-detection algorithm — analogous to
    Filtering's EMA being a simple, swappable V1 placeholder.

    sample_count (Decision 029) reflects the accelerometer series
    length — the series peak/mean/rms/jerk/cadence are all drawn from —
    not the separately-tracked gyroscope series length used only by
    peak_angular_velocity. A deliberate per-domain (not per-feature)
    simplification; see FEATURE_VALIDATION_DESIGN.md.
    """

    def extract(self, window: Window) -> DomainExtractionResult:
        accel_series: List[Tuple[float, float]] = []
        angular_velocities: List[float] = []

        for frame in window.frames:
            reading = frame.readings.get("primary_motion")
            if reading is None:
                continue
            channels = reading.filtered_channels

            if all(name in channels for name in ("accel_x", "accel_y", "accel_z")):
                ax = channels["accel_x"].value
                ay = channels["accel_y"].value
                az = channels["accel_z"].value
                resultant = math.sqrt(ax * ax + ay * ay + az * az)
                accel_series.append((frame.reference_timestamp, resultant))

            if all(name in channels for name in ("gyro_x", "gyro_y", "gyro_z")):
                gx = channels["gyro_x"].value
                gy = channels["gyro_y"].value
                gz = channels["gyro_z"].value
                angular_velocities.append(math.sqrt(gx * gx + gy * gy + gz * gz))

        features: Dict[str, float] = {}

        if accel_series:
            values = [value for _, value in accel_series]
            features["peak_resultant_acceleration"] = max(values)
            features["mean_resultant_acceleration"] = sum(values) / len(values)
            features["rms_resultant_acceleration"] = math.sqrt(sum(v * v for v in values) / len(values))

        if angular_velocities:
            features["peak_angular_velocity"] = max(angular_velocities)

        if len(accel_series) >= 2:
            jerks = []
            for (t0, v0), (t1, v1) in zip(accel_series, accel_series[1:]):
                dt_seconds = (t1 - t0) / 1000.0
                if dt_seconds > 0:
                    jerks.append(abs(v1 - v0) / dt_seconds)
            if jerks:
                features["mean_jerk"] = sum(jerks) / len(jerks)
                features["peak_jerk"] = max(jerks)

        if len(accel_series) >= 3:
            window_duration_minutes = (window.window_end - window.window_start) / 60000.0
            if window_duration_minutes > 0:
                peak_count = _count_local_maxima([value for _, value in accel_series])
                features["cadence_per_minute"] = peak_count / window_duration_minutes

        return DomainExtractionResult(features=features, sample_count=len(accel_series))
