# Phase 4: Evaluation Framework

## Purpose

Phase 4 is the permanent, algorithm-independent scientific evaluation boundary for Vikzar AI. It never trains, transforms, imputes, promotes, or changes a model, prediction, dataset, runtime object, or hardware input. Every future model submits the same immutable `PredictionSet`.

## Input contract

`PredictionSet` contains model identifier/version, Phase 3 dataset ID and split, immutable prediction rows, direct measured ground-truth rows, and `PredictionProvenance`. Every prediction references one submitted truth row by `(example_id, target_name)`. Missing predictions are measured explicitly; unknown or duplicate rows are rejected.

Ground-truth rows carry Phase 3 player, session, and split context. Optional position and drill fields support future datasets carrying that context. Evaluation never reads hardware, ETL, runtime, inference, or model implementation modules.

## Metrics, slicing, and calibration

For every target, the framework calculates MAE, RMSE, R-squared, Pearson correlation, bias, coverage, matched sample count, and missing-prediction count. Undefined R-squared or correlation is `null` with a warning; values are never invented.

`EvaluationSlice` supports player, position, drill, session, and dataset-split stratification. Overall release decisions use the complete submitted split; sliced results are diagnostic only. Optional confidence is assessed by comparing mean confidence with agreement inside a declared absolute-error tolerance. Calibration is unavailable, rather than fabricated, when confidence is absent.

## Release gates

`ReleaseGatePolicy` is external to every model and supports minimum R-squared, maximum RMSE, minimum matched sample count, and complete-prediction detection. Each target has explainable `ReleaseGateResult` records. A report is approved only when every configured gate passes. Evaluation records a decision; it never promotes a model.

## Reproducibility and storage

The report ID and embedded SHA-256 checksum derive from submitted evidence, policy, metrics, and provenance. Its timestamp is the deterministic Phase 3 dataset creation timestamp, not wall-clock execution time. Identical submitted evidence produces byte-identical report content.

`EvaluationReportStorage` writes a new local folder atomically:

```text
data/evaluations/<report_id>/
  evaluation_report.json
  checksums.json
```

The report contains its evaluation schema version, model/dataset versions, dataset-manifest checksum, timestamp, provenance, embedded checksum, metrics, warnings, failed checks, and release decision. `checksums.json` protects the stored artifact; consumers must call `verify` before using it.

## Phase 3 and hardware independence

Tests build synthetic evidence through the normal Phase 3 Dataset Builder contracts. Real verified sessions later produce the same Phase 3 dataset manifest and rows, so Phase 4 needs no architectural or code change when hardware replaces synthetic sources.
