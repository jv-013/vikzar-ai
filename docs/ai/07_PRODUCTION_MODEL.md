# Phase 7: Production Model

## Purpose

Phase 7 provides the permanent offline production-model training pipeline. It
trains a deterministic multi-output model from Phase 3 evidence, evaluates it
only through Phase 4, records it only through Phase 5, and compares it with all
permanent Phase 6 benchmarks.

The current measured targets are continuous EMG metrics. The production model
therefore estimates synchronized muscle-activity ground truth; it does not
invent an ACL injury label. Later risk-engine phases may consume validated
model outputs, but Phase 7 contains no runtime inference or risk calculation.

## Architecture

```text
Phase 3 DatasetBuildResult
        |
ProductionTrainer
        |
ProductionModelFactory
        |
DeterministicMLPRegressorAdapter
        |
Phase 5 ExperimentRunner
        |
Phase 4 EvaluationReport
        |
ProductionModelRegistry
        |
Phase 5 ExperimentComparator
        |
ProductionModelSelection
```

Phase 4 remains the only metric and release-gate authority. Phase 5 remains
the only experiment, locking, history, checksum, and artifact authority.
Phase 7 imports no ETL, hardware, inference, risk, API, cloud, Firebase,
dashboard, or deployment modules.

## Model and hyperparameters

The sole production factory type is the versioned deterministic multilayer
perceptron regressor:

```text
production.deterministic_mlp_regressor
```

`ProductionModelConfig` immutably records hidden-layer sizes, learning rate,
epoch count, L2 penalty, random seed, and Adam constants. The production
architecture uses:

- training-only feature and target z-score normalization;
- seeded Xavier-uniform initialization;
- `tanh` hidden activations and linear multi-output regression;
- deterministic full-batch Adam;
- fixed training epochs;
- lowest validation MSE with earliest-epoch tie behavior;
- no global random state, mini-batch ordering, or nondeterministic workers.

Held-out test targets are never exposed to the adapter. Validation targets may
select a checkpoint, while Phase 5 retains test truth for Phase 4 evaluation.

## Training lifecycle

`ProductionTrainer.run`:

1. Creates the adapter through `ProductionModelFactory`.
2. Creates an immutable Phase 5 `ExperimentSpec`.
3. Records dataset checksum/version, ordered schemas, model version,
   hyperparameters, seed, creator, and training timestamp.
4. Delegates exclusive locking, training execution, software/dependency
   capture, provenance, and immutable artifact storage to Phase 5.
5. Delegates every metric and release decision to Phase 4.
6. Registers a production candidate referencing the Phase 5 model and report.
7. Requires exactly one result from every Phase 6 benchmark family.
8. Delegates ranking to Phase 5 `ExperimentComparator`.
9. Stores the immutable comparison decision.

A selection is evidence, not deployment. Phase 7 never loads a model into a
runtime service and never promotes or deploys it.

## Artifact structure and loading

`ProductionModelArtifact` is a frozen, versioned contract containing:

- schema, algorithm, model, configuration, and seed identities;
- ordered hyperparameters, features, and targets;
- training-only normalization vectors;
- complete dense-layer weights and biases;
- selected epoch, deterministic losses, and evidence counts.

Artifacts are canonical sorted UTF-8 JSON with finite values and a trailing
newline. Pickle and executable serialization are prohibited.
`ProductionModelSerializer.loads` optionally verifies SHA-256, validates every
layer and schema dimension, rejects unsupported versions and noncanonical
content, and returns `LoadedProductionModel`.

Every training run serializes and reloads the artifact before creating its
Phase 4 predictions. Stored artifacts are therefore proven loadable during the
normal training path.

## Registry and provenance

`ProductionModelRegistry` does not duplicate Phase 5 history. It creates an
immutable registration referencing:

- experiment ID and configuration hash;
- dataset ID, version, and checksum;
- model ID, version, artifact reference, and checksum;
- evaluation report ID and checksum;
- Phase 5 reproducibility checksum.

Registrations are stored under model/version/experiment paths, so prior
models are never overwritten. Selection artifacts retain the complete Phase 5
comparison and its checksum.

## Benchmark selection

Selection requires exactly one Dummy Mean, Linear Regression, Ridge
Regression, and Random Forest result. Production and benchmark evidence must
share dataset checksum, feature/target ordering, evaluation split, and Phase 4
gate policy.

`ProductionModelSelector` never reads or calculates metrics. It calls the
existing Phase 5 `ExperimentComparator`; the production recommendation is
true exactly when that comparator recommends the production experiment.

## Deterministic guarantees

With identical Phase 3 evidence, configuration, seed, Python/NumPy versions,
and dependency environment, repeated training produces identical:

- configuration and model identities;
- learned weights and normalization state;
- model bytes and checksum;
- predictions and Phase 4 evaluation checksum;
- Phase 5 reproducibility checksum.

Permanent experiment IDs and timestamps remain independent audit facts.

## Testing

Phase 7 tests use normal Phase 2 and Phase 3 synthetic evidence and real Phase
6 adapters. They cover immutable configuration, factory construction,
deterministic training, serialization/loading, checksum and tamper rejection,
automatic Phase 5 registration, Phase 4 evaluation, full four-benchmark
selection, immutable production registry artifacts, and cross-experiment
reproduction.

## Limitations

- The present target is measured muscle activity, not a direct injury event.
- Training is offline and optimized for deterministic scientific audit.
- Selection does not authorize deployment.
- No runtime inference, streaming, risk engine, API, cloud, dashboard,
  hardware integration, online learning, or Phase 8 behavior exists here.
- Real-hardware adoption changes only Phase 2 inputs; downstream contracts are
  unchanged.
