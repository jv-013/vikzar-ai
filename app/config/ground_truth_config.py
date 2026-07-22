"""Configuration defaults for the offline ground-truth pipeline."""

from __future__ import annotations

# The CaptureSession records the actual value used for every session.  This
# default only makes the intended, versioned policy available to acquisition
# tooling; quality control never substitutes it for missing capture evidence.
DEFAULT_SYNC_TOLERANCE_MS = 5.0

# Contract versions are persisted with every produced training session.
CAPTURE_SESSION_SCHEMA_VERSION = "1.0.0"
GROUND_TRUTH_SCHEMA_VERSION = "1.0.0"
