# Runtime Architecture

## Purpose

This document describes how Vikzar AI operates in real time.

Unlike traditional machine learning systems that process stored datasets, Vikzar continuously processes live sensor streams.

Every subsystem operates concurrently and communicates through well-defined interfaces.

The runtime architecture is designed to satisfy strict real-time constraints while remaining modular, scalable, and fault tolerant.

---

# Runtime Components

The complete runtime system consists of:

1. Smart Shin Pad
2. EMG Band (Training Only)
3. Bluetooth Communication
4. ETL Service
5. AI Service
6. FastAPI Service
7. Dashboard
8. Cloud Service

---

# Training Mode

Player

↓

Smart Shin Pad

+

EMG Band

↓

Bluetooth BLE

↓

ETL Service

↓

FeatureVector

↓

AI Service

↓

Cloud Storage

---

# Match Mode

Player

↓

Smart Shin Pad

↓

Bluetooth BLE

↓

ETL Service

↓

FeatureVector

↓

EMG Estimation

↓

AI Prediction

↓

Dashboard

↓

Cloud

---

# Runtime Services

## BLE Receiver

Responsibilities

- Receive BLE packets
- Validate device connection
- Forward packets to ETL

Runs continuously.

---

## ETL Service

Responsibilities

- Packet Validation
- Synchronization
- Calibration
- Filtering
- Sliding Windows
- Feature Extraction
- Feature Validation

Produces one FeatureVector every 100 milliseconds.

---

## AI Service

Responsibilities

- Validation
- Knowledge Base
- Lookup Engine
- Muscle Estimation
- Feature Enhancement
- Inference
- Risk Engine

Consumes FeatureVectors continuously.

---

## Dashboard Service

Responsibilities

- Live visualization
- Player metrics
- Risk visualization
- Alerts

The dashboard must never block AI execution.

---

## Cloud Service

Responsibilities

- Store sessions
- Store FeatureVectors
- Store predictions
- Store historical analytics

Uploads operate asynchronously.

---

# Communication

FeatureVector

↓

Runtime Queue

↓

AI Service

↓

Prediction Queue

↓

Dashboard

↓

Cloud

---

# Parallel Execution

Service 1

BLE Receiver

Service 2

ETL

Service 3

AI

Service 4

FastAPI

Service 5

Dashboard

Service 6

Cloud Worker

All services execute simultaneously.

---

# Failure Handling

If Cloud fails

↓

AI continues.

If Dashboard fails

↓

AI continues.

If BLE disconnects

↓

ETL pauses.

AI waits.

No prediction is generated until FeatureVectors resume.

---

# Performance Goals

BLE Latency

<10 ms

ETL

<40 ms

AI

<30 ms

Dashboard

Real-Time

Cloud

Asynchronous

---

# Runtime Principles

- No blocking operations
- Independent services
- Low latency
- Continuous processing
- Queue-based communication
- Fault isolation