"""
FeatureModule: the strategy abstraction for computing one biomechanical
domain's features from a single Window.

See docs/development/FEATURE_EXTRACTION_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from app.etl.windowing import Window


@dataclass(frozen=True)
class DomainExtractionResult:
    """
    A FeatureModule's output: computed biomarker values plus a minimal
    sample-count metadata field (Decision 029).

    Purpose
        sample_count exists solely to let Feature Validation make
        scientifically defensible sufficiency assessments (RMS, MAV,
        cadence, jerk, impulse, loading rate, and future frequency-
        domain biomarkers all depend on how many samples actually
        contributed). It is metadata only — never a second copy of the
        raw samples, and never a duplicate of the feature values
        themselves.

    Attributes
        features: The computed biomarker values for this domain, keyed
            by name. Empty (not zero-filled) when this domain's
            required channels/roles are absent from every frame in the
            window, or the window itself is empty.
        sample_count: How many of the window's frames actually
            contributed usable data to this domain's computation. Zero
            exactly when features is empty. Reported per domain, not
            per individual feature within it — see each FeatureModule's
            own docstring for which underlying series this count
            reflects when a domain computes from more than one series
            (e.g. MotionFeatures' accelerometer series vs. its separate
            gyroscope series).
    """

    features: Mapping[str, float]
    sample_count: int


class FeatureModule(Protocol):
    """
    A stateless, domain-scoped feature computation strategy.

    Purpose
        Compute measurable, uninterpreted numerical features from one
        Window. A pure function of window alone — no constructor
        state, no mutable fields, no side effects — so the same Window
        always produces identical output (Founder Decision 5), and a
        single instance is safely shared across every synchronization
        group and every call.

    Never
        Never merges or compares across synchronization groups, never
        classifies, never estimates, never produces anything from the
        forbidden list in FEATURE_EXTRACTION_DESIGN.md (injury risk,
        fatigue classification, dominant/weak/strong limb, compensation,
        ACL probability, movement quality, coaching feedback). Those
        belong exclusively to later AI modules.
    """

    def extract(self, window: Window) -> DomainExtractionResult:
        """
        Compute this domain's features (and their sample count) from
        one Window.

        Returns an empty features mapping and sample_count=0 (never a
        zero-filled features mapping) when this domain's required
        channels/roles are absent from every frame in the window, or
        the window itself is empty — absence is never fabricated.
        """
        ...
