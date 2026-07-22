# Phase 8 — Inference Engine

## Status and scope

Phase 8 is the permanent offline runtime boundary between validated ETL feature
vectors and raw production-model predictions. It performs inference only.
Training remains owned by Phase 7, scientific evaluation by Phase 4, and
experiment history by Phase 5.

The engine does not calculate injury risk, fatigue categories, alerts,
recommendations, player status, or coaching decisions. Those are not model
predictions and remain outside Phase 8.

## Architecture

```text
ValidatedRawFeatureVector
        |
        v
InferenceRequest (feature vector + group ID)
        |
        v
Phase 7 registration + selection verification
        |
        v
Cached approved production model
        |
        v
Ordered schema mapping -> trained-model normalization -> prediction
        |
        v
InferencePrediction (model outputs + deterministic metadata + checksum)
```

Phase 8 depends only on immutable contracts from the existing local pipeline:

- `ValidatedRawFeatureVector` from the frozen validation boundary;
- the ordered Phase 3 feature and target naming convention;
- Phase 5 checksum-addressed local artifact storage; and
- Phase 7 production registration, selection, and model serialization.

It does not import hardware, cloud, API, evaluation, experiment-runner,
benchmark-training, production-training, or Risk Engine components.

## Public lifecycle

1. Construct `ApprovedModelReferences` from the Phase 7 registration and
   selection artifact references.
2. Construct `InferenceEngine` (or use `InferenceEngine.from_artifacts`) with
   the local `ExperimentArtifactStore` and those references.
3. The engine verifies and loads the approved model once.
4. Call `predict(validated_vector, group_id=...)` for one group, or
   `predict_batch(...)` with ordered `InferenceRequest` instances.
5. Consume `InferencePrediction.predictions` and its immutable lineage
   metadata. Phase 8 never interprets those values as risk.

If a feature vector has exactly one synchronization group, `predict` may infer
the group ID. A caller must provide it when multiple groups are present.

## Model loading and approval

The loader accepts only the exact Phase 7 evidence types:

- `production_model_registration`; and
- `production_model_selection`.

Before a model becomes executable, the loader verifies:

- registration and selection artifact SHA-256 values;
- canonical Phase 7 selection content checksum;
- an affirmative `production_recommended` decision;
- agreement between the selected and registered experiment IDs;
- the comparison's recommended experiment ID;
- registered model artifact type and media type;
- model artifact SHA-256 and canonical JSON representation;
- Phase 7 model ID, version, and configuration hash agreement;
- supported model and Phase 3 dataset schema versions;
- leakage-safe Phase 3 feature names (`feature__motion__...` or
  `feature__pressure__...`);
- Phase 3 target names (`target__...`); and
- model feature, target, normalization, and layer dimensions.

An engine cannot be publicly constructed from an arbitrary loaded model.
Construction always invokes the approval-aware loader.

## Input validation and feature mapping

The public request accepts only a `ValidatedRawFeatureVector` instance, not a
mapping, raw packet, ETL-internal contract, or dataset row. Phase 8 checks that
the vector still satisfies the frozen validation contract and then maps values
in the exact order stored in the approved model artifact.

The mapper:

- reads only model-declared motion and pressure biomarkers;
- does not filter, calibrate, window, engineer, infer, or impute values;
- ignores unrelated extra runtime biomarkers;
- rejects missing model features;
- rejects non-finite values;
- rejects features marked `rejected` by ETL quality control;
- accepts `questionable` values without changing them because ETL remains the
  quality authority; and
- rejects unsupported input schema versions and missing groups.

The trained Phase 7 model performs only its own persisted z-score
normalization. Phase 8 does not calculate or alter normalization state.

## Output validation and contracts

The loaded model must return one finite row per request and one value per
ordered target. Any shape mismatch or non-finite output fails closed.

`InferencePrediction` contains:

- ordered `PredictionValue` entries;
- model, approval, source-vector, player, session, group, window, and schema
  lineage in `InferenceMetadata`;
- a content-derived prediction ID; and
- a SHA-256 checksum over canonical predictions and metadata.

It contains no ground truth, evaluation metric, release decision, risk score,
alert, recommendation, or classification.

All Phase 8 Pydantic contracts and the loaded-model wrapper are immutable.

## Deterministic guarantees

Identical approved model artifacts, validated inputs, group IDs, and
`InferenceRuntimeConfig` values produce identical:

- ordered feature matrices;
- model outputs;
- prediction metadata;
- prediction IDs;
- checksums; and
- serialized prediction contracts.

No wall-clock time, random number generator, network state, or synthetic-data
flag participates in inference. The metadata timestamp is the immutable source
vector timestamp. Synthetic and future hardware-originated feature vectors
therefore follow the same public path.

## Caching and performance

Each loader owns a bounded, thread-safe least-recently-used cache keyed by the
checksums of the exact registration and selection evidence. Only fully
verified immutable models enter the cache. Concurrent publication preserves a
single cached winner, and eviction affects performance only, never prediction
content.

The engine pre-parses feature paths once, retains the loaded model, converts
each batch to one contiguous NumPy matrix, and invokes the model once per
batch. The default maximum batch size is 256 and the default model cache holds
four approved models. Both limits are immutable, versioned configuration.

Clearing or evicting the cache never changes or deletes Phase 7 artifacts.

## Failure handling

Expected failures use the Phase 8 exception hierarchy:

- `ModelApprovalError` — no affirmative matching Phase 7 decision;
- `ModelIntegrityError` — checksum or canonical artifact failure;
- `ModelCompatibilityError` — unsupported version, schema, type, or dimension;
- `ModelLoadError` — malformed Phase 7 evidence;
- `InferenceInputError` — invalid group, schema, feature, quality, value, or
  batch;
- `InferenceOutputError` — invalid model output shape or value; and
- `InferenceConfigurationError` — reserved for runtime configuration failures.

Failures are explicit and fail closed. Phase 8 never substitutes a model,
feature, target, or prediction.

## Limitations and ownership boundaries

- Phase 8 does not train, tune, compare, evaluate, approve, or promote models.
- It does not persist predictions; persistence and transport are separate
  deployment concerns.
- It does not communicate with hardware, Firebase, cloud storage, dashboards,
  APIs, or streaming transports.
- It does not calculate uncertainty because the approved Phase 7 model
  contract does not provide calibrated uncertainty.
- It does not make injury-risk or coaching decisions.

Adding future approved model adapters requires a versioned Phase 7 artifact
and an explicit Phase 8 compatibility path. It must not weaken the existing
approval, checksum, schema, or deterministic-output guarantees.

## Verification

`tests/inference/` covers immutable contracts, normal Phase 3 and Phase 7
integration, affirmative and rejected selection evidence, model and approval
checksum tampering, version compatibility, cache reuse, single and batch
prediction, byte-for-byte reproducibility, deterministic feature ordering,
missing and rejected inputs, batch bounds, and invalid model outputs.
