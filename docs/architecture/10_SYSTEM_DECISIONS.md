# System Decisions

## Purpose

This document records the major architectural decisions made during the design of Vikzar AI.

Each decision explains what was chosen, why it was chosen, and what alternatives were considered.

This document serves as the permanent engineering reference for future contributors.

---

# Decision 001

## Modular Architecture

### Decision

The entire system is divided into independent modules.

### Reason

- Easier maintenance
- Independent development
- Better testing
- Better scalability

### Modules

- ETL
- Validation
- Knowledge Base
- Lookup Engine
- Feature Enhancement
- Inference
- Risk Engine
- Cloud
- Dashboard

---

# Decision 002

## FeatureVector Contract

### Decision

FeatureVector is the official communication contract between ETL and AI.

### Reason

Separates hardware from artificial intelligence.

Any ETL implementation capable of generating a valid FeatureVector can communicate with the AI.

---

# Decision 003

## Immutable FeatureVector

### Decision

FeatureVector can never be modified after creation.

### Reason

Maintains data integrity.

Allows debugging.

Makes benchmarking reproducible.

AI-generated information is stored inside EnhancedFeatureVector instead.

---

# Decision 004

## EnhancedFeatureVector

### Decision

Feature enhancement creates a new object instead of modifying FeatureVector.

### Reason

Keeps ETL output pure.

Separates measured data from generated intelligence.

---

# Decision 005

## Separate ETL and AI

### Decision

ETL performs no AI.

AI performs no ETL.

### Reason

Single Responsibility Principle.

Independent testing.

Cleaner architecture.

---

# Decision 006

## Training vs Match Mode

### Decision

Training:

Player wears

- Smart Shin Pad
- EMG Band

Match:

Player wears

- Smart Shin Pad only.

### Reason

EMG hardware is impractical during official matches.

---

# Decision 007

## Muscle Activity Estimation

### Decision

Estimate EMG-derived metrics during matches.

### Reason

Use relationships learned during training.

Avoid requiring EMG hardware during gameplay.

---

# Decision 008

## Knowledge Base

### Decision

Store biomechanical knowledge separately from AI models.

### Reason

Knowledge changes slowly.

Models change frequently.

Keeping them separate improves maintainability.

---

# Decision 009

## Lookup Engine

### Decision

Context enrichment occurs before machine learning.

### Reason

ML models perform better when provided contextual information.

---

# Decision 010

## Feature Enhancement

### Decision

Generate advanced features before inference.

Categories include:

- Personalization
- Temporal
- Biomechanics
- Reliability

### Reason

Improve predictive performance.

---

# Decision 011

## Cloud Independence

### Decision

Cloud services are asynchronous.

### Reason

Prediction must continue even if cloud services fail.

---

# Decision 012

## Queue-Based Communication

### Decision

Modules communicate using queues.

### Reason

Loose coupling.

Independent execution.

Improved scalability.

---

# Decision 013

## Runtime Services

### Decision

Services run continuously.

Examples:

- BLE Receiver
- ETL
- AI
- Dashboard
- Cloud

### Reason

Supports real-time streaming.

---

# Decision 014

## Hardware Independence

### Decision

AI never communicates directly with hardware.

### Reason

Supports future hardware revisions without changing AI.

---

# Decision 015

## Production Quality

### Decision

Every module must satisfy:

- Scientific validity
- Low latency
- Scalability
- Maintainability

### Reason

Vikzar is intended as a production platform rather than a prototype.

---

# Architecture Principles

The following principles are mandatory throughout the project.

- Separation of Concerns
- Single Responsibility
- Immutable Data Contracts
- Modular Components
- Hardware Independence
- Cloud Independence
- Real-Time Processing
- Production-Ready Engineering
- Scientific Validity

---

# Future Decisions

Future architectural decisions should be added to this document using the same format.

Existing decisions should never be modified without documenting the reason.