# Vikzar AI

> **Real-Time AI Platform for Football Performance, Fatigue Monitoring, and Injury Risk Prediction**

---

## Overview

Vikzar AI is an intelligent sports analytics platform that combines wearable sensing, biomechanics, machine learning, and cloud computing to help players, coaches, physiotherapists, and sports scientists monitor athlete health and performance in real time.

The platform processes live movement data from wearable devices to estimate fatigue, evaluate movement quality, identify abnormal biomechanical patterns, and predict injury risk before injuries occur.

Unlike conventional wearable systems that rely solely on inertial sensors, Vikzar integrates **muscle activity (EMG)** and **motion sensing (IMU + FSR)** during training to build personalized biomechanical models for each athlete.

During competitive gameplay, players wear only the smart shin pad while Vikzar estimates muscle activity using the relationships learned during training.

---

# Vision

Build the world's most intelligent football wearable platform capable of delivering laboratory-grade biomechanical insights using lightweight wearable hardware and AI.

---

# Wearable Hardware

## Smart Shin Pad

The smart shin pad continuously captures lower-limb movement.

Sensors include:

- Inertial Measurement Unit (IMU)
- Force Sensitive Resistors (FSR)

These sensors provide metrics including:

- Linear acceleration
- Angular velocity
- Impact characteristics
- Ground contact information
- Running mechanics
- Movement dynamics

---

## EMG Band (Training Sessions Only)

During controlled training sessions, athletes additionally wear an EMG band.

The EMG system records muscle activity including:

- Quadriceps
- Hamstrings
- Additional monitored muscle groups supported by the hardware

The ETL pipeline synchronizes EMG and shin pad data to create high-quality labelled biomechanical datasets.

These datasets are later used to train AI models capable of estimating muscle activity during actual matches without requiring the athlete to wear an EMG device.

---

# Runtime Workflow

```text
                 TRAINING MODE

          EMG Band             Smart Shin Pad
      (Muscle Activity)      (IMU + FSR Sensors)
             │                      │
             └────────────┬─────────┘
                          ▼
                    ETL Pipeline
                          │
                   Feature Extraction
                          │
                    FeatureVector
                          │
                   AI/ML Pipeline
                          │
                    Cloud Platform
```

---

```text
                 MATCH MODE

          Smart Shin Pad Only
                (IMU + FSR)
                     │
                     ▼
               ETL Pipeline
                     │
               FeatureVector
                     │
          Muscle Activity Estimation
                     │
              AI Injury Prediction
                     │
             Dashboard + Cloud
```

---

# System Architecture

```
ESP32 Smart Shin Pad
        │
 Bluetooth Low Energy
        │
        ▼
 ETL Pipeline
        │
 FeatureVector (100 ms)
        │
 ┌───────────────┬────────────────┐
 │               │                │
 ▼               ▼                ▼
AI Engine     Dashboard      Cloud Platform
```

---

# AI Pipeline

**Corrected to match the actual implemented runtime path** (verified directly against `app/api/orchestration.py` — Platform Lock pass). The diagram below reflects what real requests actually go through today:

```
RawFeatureVector
      │
Validation
      │
Inference Engine (Phase 8)
      │
Risk Engine (Phase 9, ACL risk assessment)
      │
FastAPI response
      │
(optional) Firebase — via Cloud Functions, never a direct write
```

The Knowledge Base / Lookup Engine / Feature Enhancement / Muscle Activity Estimation subsystem (`app/knowledge_base/`, `app/lookup_engine/`, `app/feature_enhancement/`, `app/muscle_activity_estimation/`) is real, tested code (~2,232 lines) — it is just not called by `app/api/orchestration.py` today. Whether to wire it into the live path or retire it is an open product/architecture decision, not resolved by this correction.

---

# ETL Pipeline

The ETL system is responsible for transforming raw BLE sensor packets into clean, validated biomechanical features.

Responsibilities include:

- BLE packet reception
- Packet validation
- Time synchronization
- Sensor calibration
- Noise filtering
- Sliding window generation
- Feature extraction
- Feature validation

Output:

```
FeatureVector
```

The AI pipeline begins only after this stage.

---

# AI Pipeline Responsibilities

The AI pipeline performs:

- Input validation
- Knowledge-based enrichment
- Feature engineering
- Temporal analysis
- Personalized biomechanics
- Model inference
- Injury risk estimation
- Fatigue analysis
- Vikzar Index generation

---

# Cloud Platform

The cloud platform stores:

- Player history
- Session history
- Predictions
- Risk scores
- Model outputs
- Analytics
- Training datasets

Cloud uploads are asynchronous and never block the real-time AI pipeline.

---

# Core Design Principles

- Real-time processing
- Modular architecture
- Production-ready engineering
- Scientifically grounded feature engineering
- Immutable FeatureVector contract
- AI independent from ETL implementation
- Cloud-independent inference
- Personalized athlete modelling
- Scalable microservice-ready design

---

# Performance Targets

| Component | Target |
|-----------|--------|
| Sensor Sampling | 100 Hz |
| Feature Vector Interval | 100 ms |
| AI Processing | <30 ms |
| Dashboard Update | Real-Time |
| Cloud Upload | Asynchronous |

---

# Repository Structure

```
vikzar-ai/

app/
data/
docs/
notebooks/
scripts/
tests/

README.md
requirements.txt
main.py
```

---

# Documentation

Detailed documentation is available in the `docs/` directory.

- Project Vision
- System Architecture
- ETL Architecture
- AI Architecture (`docs/ai/01`–`10` — code-accurate; supersedes this README's high-level diagrams wherever they disagree)
- Runtime Architecture
- Cloud Architecture
- Production Bluetooth Architecture (`docs/architecture/08_PRODUCTION_BLUETOOTH_ARCHITECTURE.md`)
- Universal Pod Mounting research (`docs/research/UNIVERSAL_POD_MOUNTING.md`)
- Coding Guidelines
- Contributing Guide
- Repo Hygiene Report (`docs/development/06_REPO_HYGIENE_REPORT.md`)
- Future Roadmap

---

# Development Team

The project is organized into two primary engineering domains.

## ETL Engineering

Responsible for:

- Wearable communication
- Signal processing
- Feature extraction
- Data validation

Output:

```
FeatureVector
```

---

## AI Engineering

Responsible for:

- Knowledge modelling
- Feature enhancement
- Machine learning
- Risk prediction
- Cloud integration
- Backend APIs

Input:

```
FeatureVector
```

Output:

- Predictions
- Risk Scores
- Vikzar Index

---

# Project Status

Under active development. Honestly, as of the Platform Lock pass (bringing this repository and `vikzar-app` into one coherent architecture):

- **Real and working**: the full Phase 3–10 offline pipeline (dataset building → benchmark models → production model training → evaluation → experiment registry → inference → risk scoring → FastAPI) — 795 passing tests, verified by actually running them, not just reading the code. `scripts/bootstrap_local_artifacts.py` runs this pipeline for real (against synthetic data) to produce a bootable artifact set.
- **Real, newly added, untested against physical hardware**: a `bleak`-based BLE transport (`app/etl/receiver/bleak_transport.py`) and a Cloud-Function-calling Firebase transport (`app/api/firebase_callable_transport.py`), both implementing this pipeline's existing `BLETransport`/`FirebaseTransport` interfaces for real — no hardware or deployed Cloud Functions exist yet to exercise them against.
- **Not yet real**: any trained model artifact from real captured sessions (only synthetic-data-trained ones exist), a physically connected Universal Pod/EMG Band, and deployed Cloud Functions on the Firebase side (built and tested in the sibling `vikzar-app` repository's `functions/`, not deployed).

This repository represents the core software platform powering Vikzar AI. See `vikzar-app/DECISIONS.md` ADR-066 through ADR-070 for the cross-repo integration decisions made this pass, and `docs/development/06_REPO_HYGIENE_REPORT.md` for a pending repo-cleanup decision awaiting review.