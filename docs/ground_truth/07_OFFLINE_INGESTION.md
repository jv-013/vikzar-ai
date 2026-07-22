# Offline Ground Truth Ingestion

`GroundTruthCaptureIngestor` creates the one immutable `CaptureSession` from
a checksum-addressed JSON manifest. It is an offline preparation step and has
no connection to the runtime ETL, validation, knowledge-base, lookup, or
inference modules.

The manifest declares `capture_session_id`, `schema_version`, `captured_at`,
and exactly these source artifacts:

```text
session_metadata       devices, calibration_sessions, phases
etl_exports            array of RawFeatureVector records
emg_captures           array of EMGRecording records
synchronization_audit  one SynchronizationAudit record
drill_log              array of DrillEvent records
placement_records      array of SensorPlacementRecord records
```

Every source entry has a relative `path` and its SHA-256 checksum. Paths may
not leave the manifest directory. The ingestor validates every checksum before
parsing any source and records the manifest and source hashes in
`CaptureSession.source_sha256` for output provenance.
