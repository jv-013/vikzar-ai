# Data Flow

## Purpose

Defines how information moves through Vikzar AI.

---

# Training Data Flow

EMG Band

+

Smart Shin Pad

↓

BLE

↓

ETL

↓

FeatureVector

↓

AI

↓

Cloud

↓

Model Training

---

# Match Data Flow

Smart Shin Pad

↓

BLE

↓

ETL

↓

FeatureVector

↓

Muscle Estimation

↓

Feature Enhancement

↓

Inference

↓

Risk Engine

↓

Dashboard

↓

Cloud

---

# AI Data Flow

FeatureVector

↓

Validation

↓

Knowledge Base

↓

Lookup Engine

↓

EnhancedFeatureVector

↓

Inference

↓

Risk Engine

↓

Dashboard

---

# Cloud Data Flow

FeatureVector

↓

Queue

↓

Cloud Worker

↓

AWS

---

# Important Rule

Every module receives structured data.

No module directly accesses hardware except ETL.

No module directly accesses BLE except ETL.

The AI only receives FeatureVectors.