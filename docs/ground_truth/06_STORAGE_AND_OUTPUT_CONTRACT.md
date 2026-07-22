# Storage and Output Contract

One `VerifiedSynchronizedTrainingSession` is written to a new immutable folder:

```text
data/ground_truth/<verified_session_id>/
  aligned_windows.parquet
  labels.parquet
  session.json
  quality_report.json
  provenance.json
  checksums.json
```

`aligned_windows.parquet` is one row per accepted limb/window and carries
Smart Pod features, measured EMG features, drill context, and synchronization
evidence. Nested evidence is retained in canonical JSON columns so that it is
not lost in the tabular representation. `labels.parquet` is one row per direct
`MeasuredEMGLabel`.
The JSON documents preserve the session identity, all QC decisions, source
hashes, contract versions, and audit identity.

Phase 3 consumes only accepted Parquet rows and direct `MeasuredEMGLabel`
values. It does not re-run synchronization or manufacture labels.

The writer creates a temporary sibling folder and renames it into place only
after all artifacts are present. `checksums.json` contains SHA-256 hashes for
every data artifact (the manifest itself is intentionally excluded to avoid a
self-referential checksum). Consumers must verify this manifest before using
the output.
