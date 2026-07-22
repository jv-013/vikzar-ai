# Phase 3: Dataset Builder

## Purpose

The Dataset Builder converts one or more checksum-verified Phase 2
`VerifiedSynchronizedTrainingSession` artifacts into an immutable, versioned,
supervised training dataset. It is fully offline and does not communicate with
hardware, modify ETL output, estimate muscle activity, train a model, or use a
cloud service.

## Input boundary

The only accepted source is a Phase 2 storage folder:

```text
verified-session/
  aligned_windows.parquet
  labels.parquet
  session.json
  quality_report.json
  provenance.json
  checksums.json
```

`VerifiedSessionReader` verifies the Phase 2 checksum manifest before reading
the artifact. It also requires the label rows in `labels.parquet` to exactly
match the label provenance retained in `session.json`.

Synthetic test sessions and real hardware sessions use this identical folder
and identical `VerifiedSynchronizedTrainingSession` contract. Synthetic-data
generation belongs only in test fixtures; no Dataset Builder code branches on
data origin.

## Build policy

`DatasetBuildSpec` records the dataset name, direct measured EMG target metric
names, selected Smart Pod domains, and a deterministic split policy. Feature
domains are restricted to `motion` and `pressure`. The measured EMG domain is
never a training input.

For every accepted aligned window, the builder:

1. Flattens selected Smart Pod biomarkers into ordered `feature__<domain>__<metric>` columns.
2. Copies requested direct EMG labels into ordered `target__<metric>` columns.
3. Verifies that every requested label occurs exactly once, references the
   accepted window, and has matching source-feature-vector provenance.
4. Rejects missing, duplicate, non-finite, or schema-inconsistent values; it
   never imputes, fills, or estimates a value.
5. Assigns connected player/session evidence components to exactly one of
   train, validation, or test. If two records share either a player or a
   session identifier, they receive the same split; no player or session can
   leak across split boundaries.

The build is reproducible for the same source evidence and specification:
feature order, target order, split membership, manifest timestamp, Parquet
content, checksums, and dataset ID are deterministic. The manifest timestamp
is the latest Phase 2 source-generation timestamp, rather than wall-clock build
time. The dataset ID is derived from the canonical build specification and
Phase 2 source provenance, not from a cloud identifier.

## Output contract

`DatasetStorage` writes a new local folder atomically:

```text
data/datasets/<dataset_id>/
  features.parquet
  labels.parquet
  dataset.json
  checksums.json
```

- `features.parquet` has one row per training example with provenance IDs,
  assigned split, and only Smart Pod feature columns.
- `labels.parquet` has one row per training example with direct EMG targets.
- `dataset.json` is the immutable `VersionedTrainingDataset` manifest: schema,
  build policy, source sessions/checksums, split membership, feature/target
  schema, and example count.
- `checksums.json` records SHA-256 hashes for every data artifact. The checksum
  document excludes itself to avoid a self-referential hash.

Writes occur in a temporary sibling directory and are renamed only after all
artifacts exist. Dataset consumers must call `DatasetStorage.verify` before
using a stored dataset.

## Downstream compatibility

Phase 4 receives the immutable dataset manifest and its feature/label Parquet
artifacts. Later model adapters must preserve the `DatasetFeatureSchema` order
and may not introduce EMG target values as inputs. A real hardware transition
changes only the Phase 2 input recordings; no Phase 3 or downstream contract
changes are required.
