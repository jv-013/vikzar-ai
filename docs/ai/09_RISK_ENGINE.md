# Phase 9 — ACL Risk Engine

## Status and scope

Phase 9 is the permanent deterministic rule layer that converts validated
Phase 8 muscle-activity predictions into explainable ACL risk indicators. It
does not train or run a model, evaluate model performance, modify predictions,
or perform an external action.

The output is a decision-support indicator, not a diagnosis, medical-device
claim, return-to-play clearance, or replacement for qualified clinical
judgment.

## Architecture

```text
Phase 8 InferencePrediction history
        + immutable player/session metadata snapshots
        + versioned individual player baseline
        + mandatory clinical policy configuration
                          |
                          v
               integrity and lineage validation
                          |
                          v
      asymmetry | fatigue | workload | muscle balance
                          |
                          v
             configured weighted ACL risk score
                          |
                          v
        alerts + recommendations + full explanation
                          |
                          v
      immutable RiskAssessment + provenance + checksum
```

The public `ACLRiskEngine` accepts only `RiskAssessmentRequest`. Its
`predictions` field is a tuple of immutable Phase 8 `InferencePrediction`
contracts. It cannot accept raw IMU, raw EMG, packets, ETL windows, feature
vectors, dataset rows, model objects, or training evidence.

`RiskAssessmentRequest.from_runtime` snapshots the existing `Player` and
`Session` contracts into immutable, risk-specific metadata. Risk computation
uses the versioned `PlayerRiskBaseline`; it does not parse free-form injury
history text into a clinical rule.

## Mandatory clinical policy

The engine has no default clinical thresholds. Construction requires one
immutable `RiskEngineConfig` containing:

- a policy ID and policy version;
- explicit left/right synchronization-group IDs;
- configured quadriceps and hamstring target names;
- asymmetry and fatigue target sets;
- asymmetry, fatigue, muscle-balance, workload, and overall-risk thresholds;
- every scoring weight;
- fatigue evidence weights and minimum history depth;
- window-time conversion;
- intensity vocabulary and multipliers; and
- evidence-confidence weights.

All numeric policy values must be finite. Thresholds must be strictly ordered,
component weights must sum to exactly one, names must be unique and
deterministically ordered, and the policy is frozen during execution. The
canonical SHA-256 configuration hash appears in every output.

Threshold selection is an external clinical-governance responsibility. A
change to any threshold, weight, target, time scale, group identity, or
vocabulary produces a different configuration hash and therefore a different
assessment identity.

## Input validation

Before calculation, Phase 9 verifies:

- every Phase 8 prediction ID and content checksum;
- timezone-aware source timestamps;
- one player and session identity;
- one model ID, model version, model checksum, inference configuration, and
  target schema;
- unique predictions;
- only the configured bilateral group pair;
- a complete bilateral pair in every history window;
- all configured targets and non-negative muscle-activity prediction values;
- an individual baseline belonging to the same player; and
- a positive baseline reference for every configured group/fatigue target.

Input order is canonicalized. Mixed models, mixed sessions, unmatched limbs,
tampered predictions, incomplete baselines, unsupported targets, and invalid
values fail closed.

## Risk computation pipeline

### 1. Bilateral asymmetry

For each configured target in the latest complete bilateral window:

```text
asymmetry ratio =
    abs(left - right) / ((abs(left) + abs(right)) / 2)
```

If both values are zero, the ratio is zero. This symmetric percent-difference
formula does not select a reference limb. Each target score is linear from
zero to 100 at the policy's configured critical ratio; the component score is
the arithmetic mean of configured target scores. Category thresholds come
only from `AsymmetryPolicy`.

### 2. Fatigue indicator

For each configured group and target:

```text
positive baseline deviation =
    max(0, (latest - individual baseline) / individual baseline)

positive temporal trend =
    max(0, (latest - earliest) / individual baseline)
```

Available evidence is scaled by the policy's full-scale values and combined
using configured weights. A validated 0–100 session fatigue report may
participate. Missing optional trend or self-report evidence is excluded and
the remaining weights are renormalized. Baseline deviation is mandatory.

This is explicitly a fatigue indicator, not a physiological fatigue
measurement.

### 3. Workload indicator

The engine merges overlapping prediction-window intervals so bilateral
predictions and overlapping history never double-count time:

```text
exposure seconds = union(window intervals) × configured time scale
current load = exposure seconds × configured session-intensity multiplier
workload ratio = current load / individual typical-session load
```

Under-baseline, within-baseline, elevated, and excessive categories use only
the policy thresholds. The risk component begins increasing at the configured
elevated ratio and reaches 100 at the configured excessive ratio.

This is a within-session, individual-baseline exposure indicator. It is not an
acute:chronic workload ratio.

### 4. Muscle-balance indicator

For each configured limb group:

```text
target ratio = predicted hamstring target / predicted quadriceps target
```

Deviation outside the configured lower/upper range is scaled to 100 at the
configured critical deviation. The component uses the worse bilateral side.
It is retained as one factor only and never treated as an independent injury
prediction.

### 5. Overall score

The engine calculates five transparent components:

- asymmetry;
- fatigue;
- workload;
- muscle balance; and
- explicit prior ACL injury from the versioned baseline.

```text
risk score = Σ(component score × configured component weight)
```

The public 0–100 score is assigned `low`, `moderate`, `high`, or `critical`
using configured overall bands. `ContributingFactor` records every component
score, weight, weighted contribution, and rationale, including zero-valued
components.

## Confidence

`RiskAssessment.confidence` is evidence confidence, not model confidence or a
probability of injury. It combines:

- baseline reliability;
- available bilateral history depth; and
- required metadata completeness.

The weights are configured and sum to one. Phase 8 does not provide calibrated
model uncertainty, so Phase 9 does not invent it.

## Alert logic

Alerts are immutable local outputs; Phase 9 sends nothing externally.
Deterministic rules generate stable codes for:

- high or critical overall risk;
- high or critical asymmetry;
- high or severe fatigue indication;
- elevated or excessive workload;
- high or critical muscle-balance deviation; and
- recorded prior ACL injury context.

Alerts are ordered by severity and code. Phase 10 or another authorized
consumer may decide how to display them, but Phase 9 never invokes an API,
dashboard, Firebase, cloud service, or notification transport.

## Recommendation logic

Recommendations are deterministic human-review guidance. They may suggest:

- qualified sports-medicine review for a critical combined indicator;
- staff review before additional high-intensity work;
- repeat bilateral comparison under controlled conditions;
- recovery-context review;
- workload review against the approved individual baseline; or
- review of muscle-balance evidence alongside other clinical information.

No recommendation autonomously changes training, player status, selection, or
medical clearance. When no category exceeds its watch level, the output
recommends continuing the planned monitoring protocol.

## Output and provenance

`RiskAssessment` contains:

- risk score and category;
- evidence confidence;
- fatigue, workload, asymmetry, and muscle-balance indicators;
- triggered alerts;
- all weighted contributing factors;
- ordered recommendations;
- policy, baseline, player, session, model, inference configuration, and every
  input prediction ID/checksum;
- an assessment time derived from the latest prediction timestamp;
- a content-derived assessment ID; and
- a canonical SHA-256 checksum.

No wall-clock value participates in the output.

## Deterministic guarantees

Identical Phase 8 predictions, metadata, player baseline, player/session
contexts, and `RiskEngineConfig` produce byte-identical assessments.
Prediction input order does not affect the result. There is no random number
generator, network state, system clock, hidden mutable threshold, synthetic
data flag, training, or inference inside Phase 9.

Synthetic and future real-hardware predictions therefore use the exact same
contract and rule path.

## Scientific limitations

The design deliberately requires governed, population- and measurement-aware
thresholds:

- A systematic review found that commonly used 10–15% inter-limb asymmetry
  thresholds were not consistently evidence-based and recommended an
  individual approach:
  <https://pubmed.ncbi.nlm.nih.gov/35321131/>.
- A systematic review concluded that hamstring-to-quadriceps ratio has limited
  value as an independent ACL or hamstring-injury predictor:
  <https://pubmed.ncbi.nlm.nih.gov/35065297/>.
- Surface-EMG amplitude has important limitations as a direct representation
  of neural drive, and fatigue inference from amplitude alone requires
  caution:
  <https://pubmed.ncbi.nlm.nih.gov/33240204/> and
  <https://pubmed.ncbi.nlm.nih.gov/29233666/>.
- Football workload intervention evidence and cutoffs remain conflicting and
  lack universal consensus:
  <https://bjsm.bmj.com/content/55/2/108>.

Accordingly, Phase 9 is multi-factor, baseline-relative, transparent, and
non-diagnostic. Its scores must be validated prospectively for the intended
population, model targets, sensors, protocol, and operational use before
clinical deployment.

Phase 9 does not estimate contact risk because Phase 8 provides no
contact-event evidence. It does not fabricate unavailable biomechanical,
medical, or environmental measurements.

## Verification

`tests/risk_engine/` covers policy immutability and hashing, invalid weights
and threshold order, exact component formulas, complete weighted
explanations, low and critical scenarios, alerts, recommendations, provenance,
prediction-order independence, byte reproduction, output checksum binding,
mixed lineage, tampering, unmatched limbs, negative predictions, and missing
baselines.
