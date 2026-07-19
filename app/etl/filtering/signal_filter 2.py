"""
SignalFilter: the strategy abstraction for reducing measurement noise in
one channel's value stream while preserving genuine biomechanical
events.

See docs/development/FILTERING_DESIGN.md and
docs/architecture/10_SYSTEM_DECISIONS.md.

Noise vs. genuine biomechanical events
    Vikzar's primary purpose (detecting impacts, landings, pivots,
    cutting actions, tackles, kicking mechanics) depends on exactly the
    kind of sharp, high-magnitude, short-duration transient a careless
    noise filter is most likely to damage. Electrical/quantization
    sensor noise and a genuine impact are not cleanly separable by
    frequency content alone — both can occupy overlapping high-frequency
    bands. Correctly distinguishing them requires filter design informed
    by real, experimentally characterized noise-floor and impact-
    signature data for this specific hardware, which does not exist yet
    (the same category of gap already documented for FSR 402's
    force-conversion curve and EMG's bandpass/notch design in
    app.etl.calibration). Until that data exists, every implementation
    below defaults, via etl_config.py, to alpha=1.0 — a literal
    passthrough that cannot attenuate any signal content, impacts
    included, by construction. That default is not a placeholder
    chosen for convenience; it is the safest position available given
    what is not yet known.

Swapping the algorithm without changing the architecture
    Tightening any alpha below 1.0, or replacing a class below with a
    genuinely different filter family (a bidirectional/zero-phase
    Butterworth low-pass, a Kalman filter modeling expected impact
    dynamics, a bandpass/notch design for EMG), is a Level 1/2 change:
    implement a new SignalFilter and change only defaults.py's factory
    wiring. Filterer, FilteredFrame, FilteredReading, and every stage
    downstream of Filtering are unaffected by that swap — none of them
    know or care which concrete filter produced a value, only that it
    satisfies this Protocol.

Hardware is wearable-mounted, not shin-guard-mounted
    The Smart Pod is a universal wearable module (shin guard,
    compression sleeve, knee brace, or a future compatible wearable).
    Nothing below assumes a mounting location — only calibrated
    sensor measurements from a wearable-mounted sensor are ever
    referenced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


class SignalFilter(Protocol):
    """A stateful strategy for reducing noise in one channel's value stream."""

    def filter(self, value: float) -> float:
        """Return the filtered value for the next sample in this channel's stream."""
        ...


@dataclass
class _ExponentialMovingAverage:
    """
    Shared internal smoothing primitive.

    Not part of the public interface — IMUFilter/EMGFilter/FSR402Filter
    each wrap their own private instance so per-modality filter classes
    can evolve independently (e.g. EMGFilter later adopting a real
    bandpass/notch design) without affecting the others, even though
    all three presently use identical math.

    y[n] = alpha * x[n] + (1 - alpha) * y[n-1]. The first sample for a
    stream has no prior output to blend with, so it is returned
    unchanged (the standard bootstrap for a recursive filter).
    """

    alpha: float
    _previous_output: Optional[float] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not (0.0 < self.alpha <= 1.0):
            raise ValueError(f"alpha must be in (0.0, 1.0]; got {self.alpha!r}.")

    def apply(self, value: float) -> float:
        if self._previous_output is None:
            self._previous_output = value
            return value
        output = self.alpha * value + (1.0 - self.alpha) * self._previous_output
        self._previous_output = output
        return output


@dataclass
class IMUFilter:
    """
    V1 smoothing for accelerometer/gyroscope channels from the
    wearable-mounted Smart Pod.

    accel_x/y/z carry the primary signal for impact detection (studs
    striking ground, tackles, landings). alpha defaults to 1.0
    (etl_config.DEV_ACCEL_FILTER_ALPHA / DEV_GYRO_FILTER_ALPHA) —
    literal passthrough — specifically because no validated
    characterization of this hardware's noise floor versus genuine
    impact signatures exists yet. Do not tune alpha below 1.0 without
    that data; see this module's docstring.
    """

    alpha: float

    def __post_init__(self) -> None:
        self._ema = _ExponentialMovingAverage(alpha=self.alpha)

    def filter(self, value: float) -> float:
        return self._ema.apply(value)


@dataclass
class EMGFilter:
    """
    V1 smoothing for EMG channels from the wearable-mounted EMG Band.

    A placeholder, not a complete EMG signal-processing chain: real EMG
    noise reduction calls for a bandpass filter (roughly 20-450Hz) plus
    a powerline notch (50Hz or 60Hz depending on deployment region),
    which requires the EMG Band's actual sampling rate and deployment
    region — neither exists in this project's configuration yet.
    Inventing cutoff frequencies without that data would fabricate
    precision that doesn't exist. Kept as its own class, rather than
    sharing a generic filter with IMUFilter/FSR402Filter, specifically
    so a real bandpass/notch implementation can replace this one later
    without touching the other two or Filterer.
    """

    alpha: float

    def __post_init__(self) -> None:
        self._ema = _ExponentialMovingAverage(alpha=self.alpha)

    def filter(self, value: float) -> float:
        return self._ema.apply(value)


@dataclass
class FSR402Filter:
    """
    V1 smoothing for FSR channels from the wearable-mounted Smart Pod's
    Interlink FSR 402 sensors.

    Unlike FSR402DevelopmentCalibration (app.etl.calibration), this
    class makes no claim about the sensor's force-conversion curve —
    noise smoothing is independent of that unresolved question, so no
    "Development" qualifier is needed on the name.
    """

    alpha: float

    def __post_init__(self) -> None:
        self._ema = _ExponentialMovingAverage(alpha=self.alpha)

    def filter(self, value: float) -> float:
        return self._ema.apply(value)
