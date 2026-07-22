# Phase 10 — API and System Integration

## Final architecture

Phase 10 is the deployment and orchestration layer. It changes no scientific
or machine-learning behavior.

```text
Smart Pod / ETL process
        |
        | RawFeatureVector (already windowed and feature-extracted)
        v
Local FastAPI compute node
        |
        +-- request/schema limits
        +-- correlation ID and authentication hook
        +-- frozen RawFeatureVector validation
        +-- Phase 8 approved-model inference
        +-- Phase 9 configured ACL risk assessment
        +-- local checksum-protected session checkpoint
        |
        +--> local structured API response
        |
        `--> allowlisted Firebase summary projection (optional)
                 |
                 +-- live dashboard state
                 +-- session synchronization
                 +-- player history
                 +-- reports
                 `-- analytics
```

The laptop is the sole compute node. Firebase never receives raw packets, raw
IMU, raw EMG, feature vectors, or model feature matrices and never performs
validation, ETL, inference, or risk computation.

## Authority boundaries

- Phase 4 remains the only evaluation authority.
- Phase 5 remains the only experiment authority.
- Phase 7 remains the only production-training authority.
- Phase 8 remains the only inference authority.
- Phase 9 remains the only risk authority.
- Phase 10 validates requests, sequences those public operations, manages
  lifecycle, and synchronizes approved summaries.

Dependency injection exposes only the Phase 8 `predict_batch` and Phase 9
`assess` operations. The orchestrator contains no model, normalization,
threshold, scoring, recommendation, or alert logic.

## Request lifecycle

`POST /api/v1/sessions/{session_id}/feature-vectors` accepts a
`PipelineRequestEnvelope` containing the frozen ETL `RawFeatureVector`
contract.

The request follows one enforced path:

1. Trusted-host, request-size, correlation, and authentication middleware.
2. Pydantic request parsing.
3. Existing `validate_raw_feature_vector` semantic validation.
4. Session/player identity and bilateral-group checks.
5. Approved local player-baseline lookup.
6. One Phase 8 batch call for the configured left/right groups.
7. Local session prediction history assembly.
8. One Phase 9 assessment call.
9. Atomic local checkpoint update only after successful assessment.
10. Optional Firebase projection.
11. Structured response containing the two current predictions, complete risk
    assessment, lifecycle snapshot, synchronization status, and operational
    latency.

If any local validation, inference, or risk operation fails, no prediction
history is appended and no Firebase assessment update is attempted.

## Session lifecycle

The local lifecycle states are:

```text
start -> active
active -> disconnected       (explicit disconnect or heartbeat expiry)
disconnected -> active       (reconnect)
active/disconnected -> stopped
checkpoint -> active         (crash recovery only)
```

Session IDs are permanent and cannot be reused. A stopped session cannot be
recovered. Every transition is validated and protected by a lock.

Supported operations:

- start;
- heartbeat;
- disconnect;
- reconnect;
- stop;
- recovery from a local checkpoint; and
- graceful process termination.

Pipeline processing uses a per-session lock so concurrent feature-vector
requests cannot lose or reorder prediction history. Graceful shutdown marks
all non-stopped loaded sessions `stopped` with reason
`graceful_shutdown`, persists them, synchronizes the final lifecycle summary
when enabled, flushes queued Firebase operations, and closes the transport.

### Local recovery

`LocalSessionCheckpointStore` writes canonical JSON in an atomic replace and
stores a SHA-256 checksum over the complete payload. Checkpoints contain
player/session metadata and Phase 8 prediction history locally. They are never
sent to Firebase.

Recovery verifies the checksum and contract before restoring the session.
Corrupted, missing, duplicate, or stopped checkpoints fail closed.

## API endpoints

Public health endpoints:

- `GET /health/live` — process liveness.
- `GET /health/ready` — local inference, risk, checkpoint, and optional
  Firebase component state.

Authenticated operational endpoints:

- `GET /metrics`
- `POST /api/v1/sessions/start`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/heartbeat`
- `POST /api/v1/sessions/{session_id}/disconnect`
- `POST /api/v1/sessions/{session_id}/reconnect`
- `POST /api/v1/sessions/{session_id}/recover`
- `POST /api/v1/sessions/{session_id}/stop`
- `POST /api/v1/sessions/{session_id}/feature-vectors`

No endpoint trains, evaluates, compares, promotes, or reloads a model. No
manual cloud-upload endpoint exists. Firebase is the live-dashboard channel,
so Phase 10 intentionally exposes no competing WebSocket stream.

## Firebase responsibilities

`FirebaseSynchronizer` accepts an injected `FirebaseTransport`. Phase 10 does
not embed Firebase credentials or implement a production identity provider.

Allowed roots:

- `live/`
- `sessions/`
- `players/`
- `reports/`
- `analytics/`

Assessment projections contain only:

- timestamp, session, player, and current drill;
- ACL risk score/category and evidence confidence;
- fatigue, workload, asymmetry, and muscle-balance scores/categories;
- alert codes/severity;
- assessment ID/checksum;
- model and policy versions;
- weighted contributing factors and recommendations in reports.

A recursive guard rejects payload keys associated with raw data or feature
vectors. Writes are content-addressed with deterministic operation IDs.
Transport failures enter a bounded in-memory deferred queue without failing
local inference or risk computation. Heartbeats/reconnects and graceful
shutdown attempt to flush the queue. Queue state is observable through
`/metrics` and readiness.

For stronger restart durability, a deployment may implement the same
`FirebaseTransport` interface over a locally persistent outbound queue without
changing compute phases.

## Deployment configuration

`APISettings` is immutable and loads only `VIKZAR_*` non-secret values.
Production bootstrap requires local paths for:

- `VIKZAR_ARTIFACT_ROOT`
- `VIKZAR_MODEL_REFERENCES_FILE`
- `VIKZAR_RISK_POLICY_FILE`
- `VIKZAR_BASELINES_FILE`
- `VIKZAR_CHECKPOINT_DIRECTORY`

Important operational settings include:

- `VIKZAR_AUTH_REQUIRED`
- `VIKZAR_FIREBASE_ENABLED`
- `VIKZAR_HOST`
- `VIKZAR_PORT`
- `VIKZAR_LOG_LEVEL`
- `VIKZAR_LEFT_GROUP_ID`
- `VIKZAR_RIGHT_GROUP_ID`
- `VIKZAR_HEARTBEAT_TIMEOUT_SECONDS`
- `VIKZAR_FIREBASE_QUEUE_CAPACITY`
- `VIKZAR_MAX_REQUEST_BYTES`
- `VIKZAR_TRUSTED_HOSTS`
- `VIKZAR_CORS_ORIGINS`

Startup verifies:

- the authentication hook when authentication is required;
- the Firebase transport hook when synchronization is enabled;
- Phase 7 registration/selection/model checksums through Phase 8;
- the Phase 9 policy contract;
- agreement between API and risk bilateral group IDs;
- all baseline contracts; and
- local configuration file readability.

Startup fails closed on any mismatch.

Run the environment factory with:

```text
python main.py
```

The entry point invokes Uvicorn with the validated bind address, port, and log
level. Offline operation sets `VIKZAR_FIREBASE_ENABLED=false`. A secured
deployment assembles `ApplicationDependencies` with approved authentication
and Firebase provider adapters.

## Authentication and secrets

`Authenticator` and `SecretProvider` are interfaces only. No JWT issuer,
OAuth server, Firebase credential, private key, or production authentication
provider is implemented.

When `auth_required=true`, startup fails unless an authenticator is injected.
Health endpoints remain public. Other routes require a bearer token passed
unchanged to the injected hook. Authentication failures return a generic 401
without revealing provider details.

Secrets must be resolved by the deployment hook and must never be placed in
`APISettings`, logs, API responses, checkpoints, or Firebase summary payloads.

Trusted hosts, bounded request bodies, strict correlation IDs, constrained
CORS, immutable contracts, and generic internal errors provide additional
boundary protection.

## Structured logging and tracing

Each accepted request receives or supplies `X-Correlation-ID`. IDs are
validated and echoed in the response.

Operational logs are JSON and include:

- UTC timestamp;
- severity;
- logger and event;
- correlation ID;
- method and path;
- status and duration; and
- selected non-secret session/player identifiers where explicitly supplied.

Request bodies, bearer tokens, secrets, raw sensor data, feature values,
predictions, and clinical details are never logged.

## Monitoring

`/metrics` exposes process-local:

- total and failed requests;
- pipeline requests and failures;
- aggregate pipeline latency;
- deferred Firebase operation count; and
- active session count.

Liveness indicates that the process can serve. Readiness reports Phase 8,
Phase 9, local checkpointing, and Firebase separately. Optional Firebase
degradation does not make the local compute node unready.

## Failure handling

Stable JSON errors include a machine code, safe message, correlation ID, UTC
timestamp, and optional validation paths.

Representative mappings:

- malformed request: `422 API_VALIDATION_FAILED`;
- invalid correlation ID: `400 API_INVALID_CORRELATION_ID`;
- authentication failure: `401 API_UNAUTHORIZED`;
- unknown session: `404 SESSION_NOT_FOUND`;
- invalid lifecycle transition: `409 SESSION_CONFLICT`;
- invalid/tampered pipeline input: `422 PIPELINE_INPUT_REJECTED`;
- oversized request: `413 API_REQUEST_TOO_LARGE`; and
- unexpected internal failure: `500 API_INTERNAL_ERROR`.

Unexpected errors are logged by type without returning stack traces or secret
content.

## Determinism

Phase 8 predictions and Phase 9 assessments retain their existing
deterministic guarantees. Phase 10 adds operational timestamps, latency, trace
IDs, and delivery status, but none is supplied to inference or risk
computation. Repeating identical scientific inputs and configurations
therefore yields identical prediction and assessment contracts.

## Remaining non-software work

Software completion does not constitute medical or field validation. Before
deployment decisions may be trusted, the project still requires:

- hardware integration and sensor validation;
- real Smart Pod acquisition and end-to-end latency testing;
- prospective football field testing;
- population-specific model evaluation;
- clinical policy and threshold approval;
- privacy, security, and regulatory review;
- production authentication-provider implementation;
- production Firebase transport/credential implementation; and
- operational backup, incident-response, and retention policies.
