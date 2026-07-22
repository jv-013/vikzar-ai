# Cloud Architecture

## Purpose

The cloud platform stores, manages, and analyzes long-term athlete data.

Cloud services never participate in real-time inference.

The AI pipeline must continue operating even if cloud connectivity is lost.

---

# Responsibilities

The cloud stores:

- Player profiles
- Training sessions
- Match sessions
- FeatureVectors
- Predictions
- Vikzar Index history
- Historical analytics
- Model versions

---

# Cloud Pipeline

FeatureVector

↓

Upload Queue

↓

Cloud Worker

↓

AWS

---

# AWS Services

Amazon S3

Stores:

- Raw datasets
- Processed datasets
- Model artifacts

---

Amazon DynamoDB

Stores:

- Live sessions
- Player metadata

---

Amazon RDS

Stores:

- Historical analytics
- Reports
- Long-term statistics

---

CloudWatch

Stores:

- Logs
- Runtime monitoring
- Errors

---

Future

Amazon SageMaker

Model retraining.

---

# Design Principles

Cloud is optional.

AI is mandatory.

Cloud failure must never interrupt:

- ETL
- AI
- Dashboard

---

# Upload Strategy

FeatureVectors are queued.

A Cloud Worker uploads data independently.

This prevents network delays from affecting real-time prediction.

---

# Future Extensions

- Team dashboards
- Club analytics
- Athlete comparison
- Automatic retraining
- Remote monitoring