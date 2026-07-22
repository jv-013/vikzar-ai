# Phase 6: Benchmark Models

## Purpose

Phase 6 establishes permanent scientific reference models for Vikzar AI.
They answer whether later algorithms provide meaningful improvement over a
trivial reference, an unregularized linear relationship, a regularized linear
relationship, and a simple nonlinear tree ensemble.

These models remain in the final architecture as reproducible benchmarks.
They are not runtime or production-inference models, and Phase 6 does not
implement deployment, deep learning, production ensembles, online learning,
risk prediction, or model promotion.

## Target formulation

Phase 3 currently produces continuous, directly measured EMG targets such as
quadriceps and hamstring RMS activity. Phase 6 therefore implements
multi-output regression benchmarks only. It does not invent classification
labels or discretize continuous ground truth. A future classification target
contract may add separate classification adapters without changing these
permanent regression benchmarks.

## Architecture

```text
Phase 3 DatasetBuildResult
        |
BenchmarkTrainer
        |
ExperimentSpec + Benchmark ModelAdapter
        |
Phase 5 ExperimentRunner
        |
Phase 4 EvaluationFramework
        |
Immutable ExperimentResult and model artifact
```

Phase 6 depends only on immutable Phase 3 data contracts and the permanent
Phase 5 adapter protocol. It never imports ETL, hardware, runtime inference,
risk, API, or cloud modules.

`BenchmarkTrainer` automatically creates the immutable `ExperimentSpec` from
the dataset manifest and adapter configuration. It then delegates locking,
registration, execution history, provenance, artifact storage, checksum
generation, duplicate-configuration detection, and recovery to Phase 5.

All metrics, slicing, release gates, warnings, and release decisions are
produced only by Phase 4. No evaluation formula exists in Phase 6.

## Supported permanent benchmarks

### Dummy Mean Regressor

Algorithm identifier:

```text
benchmark.dummy_mean_regressor
```

Predicts each target's mean over the training split. This is the minimum
performance reference. A useful learned model should outperform it.

### Ordinary Linear Regression

Algorithm identifier:

```text
benchmark.linear_regression
```

Fits multi-output ordinary least squares with optional intercept using a
deterministic NumPy least-squares solve. It measures the strength of a direct
linear relationship between Smart Pod features and measured EMG targets.

### Ridge Regression

Algorithm identifier:

```text
benchmark.ridge_regression
```

Fits closed-form multi-output L2-regularized regression. The intercept is not
penalized. Ridge remains a permanent reference for linear performance under
correlated or weakly conditioned biomechanical features.

### Random Forest Regression

Algorithm identifier:

```text
benchmark.random_forest_regressor
```

Fits a deterministic bootstrap ensemble of multi-output CART regression trees
using squared-error splits. Tree count, maximum depth, minimum split and leaf
sizes, feature fraction, bootstrap policy, and seed are immutable
hyperparameters. Training and prediction are single-process and deterministic.

This forest is intentionally a transparent benchmark rather than a production
ensemble. It does not implement boosting, stacking, online updates, or
hardware-specific behavior.

## Training and target isolation

The Phase 5 request supplies:

- ordered labeled training examples;
- labeled validation examples when validation is not held out;
- feature-only rows for the held-out evaluation split.

Each adapter validates feature and target names against the Phase 3
`DatasetFeatureSchema`, builds finite `float64` matrices in exactly that order,
and verifies that its algorithm, hyperparameters, and seed exactly match the
immutable experiment specification.

Held-out measured targets are never available to model adapters. Phase 5
retains those values and constructs the `PredictionSet` submitted to Phase 4.

## Deterministic artifacts and loading

Every benchmark produces a versioned `BenchmarkModelArtifact` containing:

- model schema version;
- algorithm, model, and configuration identities;
- random seed and ordered hyperparameters;
- exact feature and target schemas;
- learned constants, coefficients, or complete tree structure.

Artifacts use canonical sorted UTF-8 JSON with finite numbers and a trailing
newline. Pickle is not used. Loading therefore does not execute arbitrary
serialized Python code.

`BenchmarkModelSerializer.loads`:

1. optionally verifies the expected SHA-256 checksum;
2. validates the immutable artifact schema and algorithm-specific payload;
3. rejects unsupported versions, noncanonical JSON, incomplete trees,
   dimension mismatches, and non-finite values;
4. returns `LoadedBenchmarkModel`.

Every adapter serializes and reloads its trained artifact before generating
evaluation predictions. Successful experiment execution therefore proves that
the stored artifact is loadable and prediction-capable.

## Reproducibility guarantees

Identical Phase 3 evidence, configuration, seed, NumPy/Python versions, and
software environment produce:

- the same Phase 5 configuration hash;
- the same learned predictive state;
- byte-identical model artifact content;
- the same model SHA-256 checksum;
- identical predictions;
- the same Phase 4 report checksum;
- the same Phase 5 reproducibility checksum.

The permanent experiment ID and execution timestamps remain separate audit
facts. Two unique experiment IDs may share a configuration hash and all
scientific checksums; Phase 5 records the second run and warns that its
configuration already exists.

Random Forest randomness uses a local NumPy generator seeded only from the
recorded experiment seed. It never reads global random state.

## Experiment and evaluation evidence

Every `BenchmarkTrainer.run` automatically persists through Phase 5:

- experiment ID and configuration hash;
- dataset ID, version, and checksum;
- feature and target schema versions;
- algorithm identifier and ordered hyperparameters;
- random seed;
- Python, application, platform, and dependency versions;
- model artifact and checksum;
- Phase 4 evaluation report and checksum;
- execution metadata and append-only lifecycle history;
- full provenance and reproducibility checksum.

Artifacts are immutable and never overwrite history. Experiment locking,
interrupted recovery, duplicate-ID rejection, and identical-configuration
detection are inherited unchanged from Phase 5.

Phase 4 release approval remains informational for benchmarks. It never
deploys or converts a benchmark into a production model.

## Testing

Tests use synthetic sessions only through the normal Phase 2 and Phase 3
pipeline. Fixed timestamps and split policy make the evidence reproducible.
Coverage includes:

- exact Dummy Mean behavior;
- known multi-output Linear Regression coefficients and predictions;
- Ridge regularization and invalid configuration handling;
- Random Forest deterministic fitting and prediction;
- canonical serialization and loading for every benchmark;
- checksum mismatch, noncanonical JSON, and tampered-payload rejection;
- automatic Phase 5 experiment registration and immutable artifacts;
- byte/checksum reproduction under separate experiment IDs;
- exclusive Phase 4 evaluation and release-gate integration;
- complete repository regression testing.

## Limitations

- Benchmarks operate offline on Phase 3 datasets; they are not runtime
  inference adapters.
- Current contracts support continuous regression targets only.
- No feature selection, hyperparameter search, ensembling, calibration repair,
  or data imputation occurs.
- Random Forest training prioritizes deterministic transparency over
  large-scale optimization.
- Scientific benchmark performance does not authorize production deployment.

Replacing synthetic source sessions with real hardware evidence changes only
the Phase 2 input source. Phase 3 datasets and all Phase 4–6 contracts remain
identical.
