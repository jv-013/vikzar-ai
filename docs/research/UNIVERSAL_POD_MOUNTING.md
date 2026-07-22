# Universal Pod Mounting — Calibration, Orientation, and Feature-Extraction Impact

## Purpose

The product now describes one physical hardware module — the "Universal Pod" — that may be mounted in a Shin Guard, a Compression Sleeve, or Compression Shorts. This document determines, precisely, whether that mounting flexibility changes calibration, preprocessing, orientation transforms, feature extraction, or inference — and recommends the cleanest production solution. It is a **research/documentation deliverable only**; no code in this repository changes as a result of it. `app/etl/calibration/` remains at its current dev-placeholder (identity-transform) state, since a real per-mount calibration profile requires calibration-rig data against real hardware, which does not exist yet.

## Starting fact this analysis is built on

`docs/research/SENSOR_SPECIFICATIONS.md` — written before "Universal Pod" existed as a product concept — already documents the intended hardware precisely: a **"Smart Shin Pad"** (not a generic pod) carrying an **IMU** (acceleration + angular velocity) and an **FSR** (ground-contact force). The FSR's entire purpose — "Ground Contact Force," "Foot Strike," "Landing," "Push-off," "Contact Timing" — is physically meaningless unless the sensor sits close to the foot/ground-contact pathway. **An FSR cannot sense ground-contact force from a hip mount.** This is a hard physical constraint, not a software design choice, and it's the single most important fact for everything below.

## Per-concern analysis

### 1. Electronics calibration (`app/etl/calibration/`) — does NOT change by mount location

The calibration stage corrects for one physical Pod unit's own sensor tolerances: accelerometer/gyroscope scale, offset, and (eventually) temperature compensation. This is intrinsic to the electronics — it doesn't know or care where on the body the Pod is worn. `app/config/etl_config.py`'s current dev placeholders (`DEV_*_FILTER_ALPHA = 1.0`, identity calibration coefficients) can stay a single per-Pod-unit profile regardless of mount. **No change needed here for mounting flexibility itself.**

### 2. Orientation transform (sensor-frame → anatomical-frame) — DOES change by mount location, within a body segment

An IMU reports acceleration/angular velocity in its own local X/Y/Z frame, which depends on exactly how the physical unit sits once inserted into a garment's pocket. A rigid shin-guard insert holds the Pod in a consistent, repeatable orientation; a compression sleeve's fabric pocket allows more slip/rotation session-to-session and even within a session (fabric stretch under load). **Shin guard and compression sleeve are the same body segment (lower leg/tibia)** — a garment-specific but anatomically-consistent orientation correction is a reasonable model for both.

### 3. Compression Shorts — a different body segment, not just a different angle

A shin guard/sleeve mount tracks the **tibia**; compression shorts mount at the **hip/pelvis** — a fundamentally different body segment with different kinematics (lower-frequency, larger-amplitude rotational hip movement vs. higher-frequency tibial impact spikes). This is not an orientation-offset problem solvable by a rotation matrix — it's a different signal *source*. Combined with the FSR constraint above (§ starting fact), compression-shorts mounting cannot produce the same feature set the shin/sleeve mount produces: no meaningful ground-contact-force data, and IMU features (`peak_resultant_acceleration`, impact-detection thresholds, etc.) would carry entirely different normal ranges and clinical meaning.

### 4. Feature extraction (`app/etl/feature_extraction/motion_features.py`, `pressure_features.py`) — formulas are mount-agnostic; their *meaning* is not

The extraction math (resultant acceleration, jerk, angular velocity variance, etc.) is generic vector arithmetic — it runs identically regardless of mount. What changes is what the resulting numbers *mean*: "peak resultant acceleration of 8g" describes a tibial impact event at the shin, and something anatomically unrelated at the hip. **No code change needed in the extraction formulas themselves**; the risk is entirely in silently reusing the same downstream thresholds/baselines across mounts that produce non-comparable numbers.

### 5. Risk Engine thresholds and the production model — this is where a wrong mount silently corrupts output

`docs/ai/09_RISK_ENGINE.md` and the product's ACL-risk framing are built on lower-limb/tibial mechanics — this matches real ACL-risk sports-science literature, which centers on knee/tibial landing and cutting kinematics, not hip motion. The production model (`app/models/production/`) was (or will be) trained on data from whatever mount location the ground-truth capture sessions used. Feeding it features from a *different* mount location is a silent distribution shift: the model has never seen that data shape, and nothing in the current pipeline detects or flags this. This is the one place "Universal Pod" mounting flexibility could produce a genuinely fabricated-looking output — a real number, computed by a real model, describing something the model was never validated against.

## Recommendation — the cleanest production solution

1. **Keep the hardware genuinely universal** (one manufactured unit, usable in any of the three garments) — that's a real, valuable hardware-cost and logistics win, and nothing above argues against it at the *hardware* level.

2. **Scope the ACL-risk product use case to lower-leg mounting only** (shin guard or compression sleeve — anatomically equivalent for this purpose). This is the one recommendation that actually resolves the FSR physical constraint and the model-validity risk cleanly, rather than working around them: don't claim clinical validity for a mount location the sensor suite and the trained model were never built for. Compression-shorts mounting, if supported at all, should be treated as an explicitly separate, not-yet-validated use case (e.g., general activity/load tracking) — never silently fed into the same ACL risk pipeline as if interchangeable.

3. **Prefer self-calibrating orientation over fixed per-garment matrices.** Rather than hand-tuning three fixed orientation-correction constants (unvalidated without real calibration-rig data, and still sensitive to pocket-to-pocket/player-to-player variation), use a short, standard "reference pose" step at session start — a few seconds stationary, letting the accelerometer's gravity reading establish the sensor's tilt relative to vertical. This is a well-established IMU technique (the same idea many sports wearables already use for shoe/attachment self-calibration), and it's robust to shin-guard-vs-sleeve variation without needing three separate hardcoded profiles.

4. **Add explicit mount-location provenance and a compatibility check, matching the pipeline's own existing discipline.** `HardwareProvenance` (`app/schemas/hardware_provenance.py`) currently carries `firmware_revision`/`hardware_revision`/`protocol_version` but no mount-location field — this is a real, additive schema gap, not something to silently patch in this pass (that schema is the locked ETL→AI boundary; changing it needs explicit sign-off, per this document's own scope). The recommendation is to add a `mount_location` field there once prioritized, and have `app/inference/model_loader.py`'s existing compatibility-checking discipline (it already raises `ModelCompatibilityError` for schema-version mismatches) refuse — or clearly low-confidence-flag — any inference request whose mount location doesn't match what the loaded production model was actually trained on. This extends a pattern the codebase already trusts, rather than inventing a new one.

## What this document does not do

It does not change `app/etl/calibration/`'s current identity-transform placeholders (real per-mount calibration needs real calibration-rig data). It does not add `mount_location` to `HardwareProvenance` (a locked-boundary schema change requiring explicit sign-off). It does not retrain or alter the production model. It is research and a recommendation, per the brief's own instruction for this section.
