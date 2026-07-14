# ETL Architecture

## Purpose

The ETL pipeline converts raw wearable sensor packets into validated FeatureVectors.

The ETL pipeline is the only component allowed to interact directly with hardware.

The AI pipeline never performs ETL.

---

# Inputs

Training

• Smart Shin Pad

• EMG Band

Gameplay

• Smart Shin Pad

---

# Processing Pipeline

BLE Receiver

↓

Packet Validation

↓

Synchronization

↓

Calibration

↓

Filtering

↓

Sliding Window

↓

Feature Extraction

↓

Feature Validation

↓

FeatureVector

---

# Responsibilities

Receive BLE packets

Validate packets

Synchronize multiple sensors

Calibrate sensors

Remove noise

Generate sliding windows

Extract biomechanical features

Validate generated features

Publish FeatureVectors

---

# Output

FeatureVector

Every 100 milliseconds.

---

# Rules

ETL never performs AI.

ETL never predicts injuries.

ETL never estimates muscle activity.

ETL only produces validated FeatureVectors.

---

# Communication

After FeatureVector generation

↓

FeatureVector Queue

↓

AI Pipeline

↓

Cloud Upload

Both operate independently.