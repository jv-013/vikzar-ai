"""Central configuration for the Vikzar AI ETL pipeline.

The ETL imports configuration rather than embedding runtime policy in a
pipeline stage. Values explicitly marked as development placeholders do not
claim device-characterization or scientific validity; they preserve data
lineage until approved hardware calibration data is available.
"""

# Logical identifiers used by the development wire protocol and transport
# abstraction. They are application identifiers, not BLE hardware addresses.
SMART_POD_DEVICE_ID = "smart_pod"
EMG_BAND_DEVICE_ID = "emg_band"

# BLE connection policy.
BLE_CONNECTION_TIMEOUT_SECONDS = 5.0
BLE_RECONNECT_MAX_ATTEMPTS = 3
BLE_RECONNECT_BACKOFF_SECONDS = 1.0

# V1 runtime timing. The 100 Hz sampling rate and 100 ms output interval are
# defined by the frozen project architecture. Sensor-derived feature schemas
# document one-second sliding analysis windows.
NOMINAL_SAMPLE_INTERVAL_MS = 10.0
WINDOW_DURATION_MS = 1000.0
WINDOW_STRIDE_MS = 100.0

# Synchronization is an ETL buffering policy, not a biomechanical threshold.
SYNC_TOLERANCE_MS = 5.0
SYNC_TIMEOUT_MS = 100.0

# Development-only calibration coefficients. These are identity transforms;
# FSR output remains explicitly tagged as a development placeholder by its
# calibration implementation, rather than being represented as force.
DEV_ACCEL_SCALE = 1.0
DEV_ACCEL_OFFSET = 0.0
DEV_GYRO_SCALE = 1.0
DEV_GYRO_OFFSET = 0.0
DEV_EMG_SCALE = 1.0
DEV_EMG_OFFSET = 0.0
DEV_FSR402_SCALE = 1.0
DEV_FSR402_OFFSET = 0.0

# Passthrough filtering avoids attenuating genuine impacts or applying an
# unvalidated EMG filter before hardware-specific signal characterization.
DEV_ACCEL_FILTER_ALPHA = 1.0
DEV_GYRO_FILTER_ALPHA = 1.0
DEV_EMG_FILTER_ALPHA = 1.0
DEV_FSR402_FILTER_ALPHA = 1.0

# This V1 quality rule is documented as a conservative, non-clinical
# provisional policy within the feature-validation module.
MINIMUM_SAMPLE_COUNT_FRACTION = 0.5
