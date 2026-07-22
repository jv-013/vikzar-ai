# Phase 5: Experiment Framework

## Purpose

Phase 5 is the permanent offline orchestration boundary for reproducible model
experiments. It records exactly what a model adapter received and produced,
delegates scientific measurement to the Phase 4 Evaluation Framework, and
preserves immutable evidence for comparison and audit.

The framework does not implement an ML algorithm, calculate evaluation
metrics, modify a Phase 3 dataset, promote a model, communicate with hardware,
perform runtime inference, or require cloud services.

## Dependency boundary

```text
Verified Phase 3 dataset
        |
ExperimentSpec + ModelAdapter
        |
ExperimentRunner
        |
Phase 4 EvaluationFramework
        |
Immutable ExperimentResult
```

The dependency direction is offline and one-way. Runtime, ETL, inference,
hardware, and cloud modules never import Experiment Framework internals.
Synthetic and real sessions are indistinguishable by Phase 5 because both
arrive through the same versioned Phase 3 contracts.

## Permanent identity and configuration identity

Every experiment has two different identifiers:

1. `experiment_id` is a safe, human-assigned permanent identity. Once registered
   locally, it is never accepted as a new experiment again. Interrupted or
   failed attempts may be explicitly recovered under that same identity, but
   completed history cannot be reused.
2. `configuration_hash` is a canonical SHA-256 digest of the dataset checksum,
   feature and target schema versions, evaluation framework version, held-out
   evaluation split, algorithm identifier, ordered hyperparameters, and random
   seed. It excludes the experiment ID, notes, creator, and timestamps.

Different permanent IDs may therefore share a configuration hash. The registry
indexes all such IDs and the runner emits a deterministic warning instead of
overwriting or silently suppressing the new experiment. This preserves the
full audit trail while detecting accidental duplicate configurations.

## Exclusive execution locking

Before reading or mutating registry or experiment artifacts, the runner creates:

```text
registry/<experiment_id>/running.lock
```

Creation uses the operating system's exclusive-create operation. A second
process or thread using the same experiment ID fails immediately with
`ExperimentLockError`; it never waits and never writes an artifact. The lock
records the experiment ID, process ID, and a private owner token. Only the
owning lease may release it.

Normal completion, controlled interruption, and handled failure release the
lock. A process terminated without cleanup intentionally leaves a fail-closed
lock. An operator must verify that no execution is active before resolving
such a stale operating artifact; experiment evidence is never deleted or
overwritten automatically.

## Adapter protocol and target isolation

`ModelAdapter` is the stable extension point for Phase 6 and every later model
family. An adapter declares an `algorithm_identifier` and implements
`execute(ModelExecutionRequest)`.

The request contains:

- the immutable experiment specification;
- the Phase 3 dataset manifest;
- labeled training examples;
- labeled validation examples only when validation is not the held-out split;
- feature-only `ModelInputRow` objects for the held-out evaluation split.

Measured targets for the held-out split are never exposed to an adapter. The
runner retains them, constructs the immutable Phase 4 `PredictionSet` after the
adapter returns prediction rows, and verifies exact dataset, model, split,
feature-schema, target-schema, and checksum lineage.

An adapter returns only algorithm-neutral `ModelAdapterOutput`: model identity
and version, ordered schemas, deterministic model bytes, prediction rows, and
execution metadata. Baseline ML, deep learning, and future algorithms can
implement this interface without changing Phase 5.

## Execution and evaluation

For each attempt, the runner:

1. Acquires the permanent-ID lock.
2. Detects previously registered matching configuration hashes.
3. Records the software, platform, and dependency environment.
4. Registers the immutable spec or validates explicit recovery.
5. Appends a `running` lifecycle event.
6. Validates Phase 3 lineage and prepares target-isolated adapter input.
7. Executes the injected model adapter.
8. Constructs an unmodified Phase 4 `PredictionSet`.
9. Delegates evaluation to `EvaluationFramework`.
10. Verifies the returned report and embedded checksum.
11. Stores model, evaluation, and result artifacts.
12. Appends `completed`, `failed`, or `interrupted` lifecycle evidence.
13. Releases the lock.

Models do not promote themselves. `PromotionRecommendation` only mirrors the
external Phase 4 release decision and reasons. Any real promotion remains a
separate manual or future deployment workflow.

## Registry, recovery, and storage

The local artifact layout is:

```text
registry/<experiment_id>/
  spec.json
  attempt-0001-running.json
  attempt-0001-completed.json

configuration_index/<configuration_hash>/
  <experiment_id>.json

experiments/<experiment_id>/attempt-0001/
  model.bin
  evaluation_report.json
  result.json

comparisons/
  <comparison_id>.json
```

Registry lifecycle snapshots are append-only. A failed or interrupted
experiment may be restarted only with `recover=True` and the exact registered
`ExperimentSpec`. Recovery creates a new numbered attempt and records
`recovered_from_run_id`; it never edits the earlier attempt. Running or
completed experiments cannot be silently reused. After an operator has safely
resolved a stale fail-closed lock, explicit recovery converts any orphaned
`running` attempt into an append-only `interrupted` event before starting the
next attempt. Completed experiments are never recoverable.

Artifact writes use staging files and atomic rename. Existing paths accept only
byte-identical content; conflicting content raises `ExperimentStorageError`.
Every `ArtifactReference` carries a SHA-256 checksum and can be verified before
use. Paths are constrained to the configured local root.

## Reproducibility

Execution timestamps and permanent experiment IDs remain audit facts and may
differ between two executions. Scientific reproducibility is represented by
`reproducibility_checksum`, which binds:

- configuration hash;
- Phase 3 dataset checksum;
- model identity and version;
- exact feature and target ordering;
- model artifact checksum;
- Phase 4 evaluation report checksum.

Two permanent experiments with the same configuration and deterministic
adapter output have the same configuration, model, evaluation, and
reproducibility checksums even though their history paths and timestamps are
different.

The environment snapshot permanently records Python, application, platform,
and declared dependency versions so output differences can be investigated.

## Comparison

`ExperimentComparator` consumes completed immutable `ExperimentResult`
contracts. It considers only candidates approved by their external Phase 4
release gates, recommends the lowest mean overall RMSE, and produces a
deterministic checksum-bound `ExperimentComparison`. It performs no training,
evaluation, artifact mutation, or promotion.

## Testing

Phase 5 tests build synthetic sessions through the normal Phase 2 and Phase 3
pipeline. No experiment-specific dataset generator exists in production code.
Deterministic mock adapters verify:

- immutable contracts and configuration hashes;
- permanent experiment-ID rejection;
- identical-configuration detection;
- exclusive lock contention;
- held-out target isolation;
- deterministic execution and reproduction;
- artifact registration and tamper detection;
- interrupted and failed attempt recovery;
- schema, algorithm, dataset, and report compatibility;
- provenance preservation;
- deterministic comparison and manual-only promotion.

Replacing synthetic acquisition with real hardware changes only Phase 2 input
evidence. The Phase 3, Phase 4, Phase 5, and future adapter contracts remain
unchanged.
