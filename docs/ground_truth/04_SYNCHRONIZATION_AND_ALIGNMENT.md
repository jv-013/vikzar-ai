# Synchronization and Alignment

The acquisition workflow writes one `SynchronizationAudit` inside the
`CaptureSession`. It records the time reference, applied tolerance, and an
observation for every Smart Pod feature-vector/group candidate.

Each matched observation includes the primary timestamp, EMG timestamp, and
absolute alignment error. A window is eligible only when it is matched, its
recorded alignment error is within the session-recorded tolerance, and its
measured EMG domain is present.

Before a verified session is built, the offline pipeline checks that every
audit observation references a real ETL vector/group candidate. For every
matched observation it independently verifies that the recorded absolute error
equals the difference between the two recorded timestamps (within 0.001 ms).
It never repairs an audit or derives a replacement timestamp.

ETL `RawFeatureVector.timestamp` is publish-time provenance only. Alignment is
based on the feature window boundaries and capture-side synchronization audit,
never reconstructed from publication timestamps.
