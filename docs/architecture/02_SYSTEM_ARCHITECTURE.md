# System Architecture

## Purpose

This document defines the overall software architecture of Vikzar AI.

The architecture separates Hardware, ETL, AI, Cloud, and Dashboard into independent modules that communicate through well-defined interfaces.

---

# System Overview

Vikzar AI consists of five major subsystems.

1. Wearable Hardware
2. ETL Pipeline
3. AI Pipeline
4. Cloud Platform
5. Dashboard

---

# Training Mode

During training sessions the player wears:

• Smart Shin Pad
• EMG Band

Both sensor streams are synchronized by the ETL pipeline.

The generated FeatureVector contains both movement and muscle information.

This data is stored for AI model training.

---

# Match Mode

During competitive gameplay the player wears only the Smart Shin Pad.

The AI estimates muscle behaviour using models trained during training sessions.

No EMG hardware is required during matches.

---

# Runtime Pipeline

Smart Shin Pad + EMG Band
            │
            ▼
Bluetooth BLE
            │
            ▼
ETL Pipeline
            │
      FeatureVector
            │
      ┌─────┴─────┐
      │           │
      ▼           ▼
 AI Pipeline   Cloud Upload
      │
      ▼
 Dashboard

---

# AI Pipeline

FeatureVector

↓

Validation

↓

Knowledge Base

↓

Lookup Engine

↓

Feature Enhancement

↓

EnhancedFeatureVector

↓

Inference

↓

Risk Engine

↓

Vikzar Index

↓

FastAPI

↓

Dashboard

---

# Core Principles

• Modular Design

• Immutable FeatureVector

• AI independent of ETL

• Cloud independent of AI

• Real-Time Processing

• Production Ready

• Scientifically Grounded