# Project Rules

## Purpose

This document defines the mandatory engineering rules followed throughout the Vikzar AI project.

Every contributor must follow these rules.

Violation of these rules requires discussion before merging.

---

# Rule 1

FeatureVector is immutable.

Never modify a FeatureVector.

Create an EnhancedFeatureVector instead.

---

# Rule 2

ETL performs only ETL.

Never add AI logic inside ETL.

Responsibilities include

- BLE
- Validation
- Synchronization
- Calibration
- Filtering
- Sliding Window
- Feature Extraction

Nothing else.

---

# Rule 3

AI never communicates directly with hardware.

Hardware

↓

ETL

↓

FeatureVector

↓

AI

Always.

---

# Rule 4

Cloud is optional.

Prediction is mandatory.

If AWS becomes unavailable

↓

AI continues.

---

# Rule 5

Dashboard never blocks prediction.

Dashboard failures must not interrupt AI.

---

# Rule 6

No hardcoded values.

All constants belong inside

app/config

---

# Rule 7

Every module has one responsibility.

Avoid large classes performing multiple unrelated tasks.

---

# Rule 8

Every public function requires

Purpose

Arguments

Returns

Type hints

Docstrings

---

# Rule 9

Every new feature requires

Research

↓

Design

↓

Documentation

↓

Implementation

↓

Testing

↓

Integration

---

# Rule 10

Every module must have unit tests.

Critical modules require integration tests.

---

# Rule 11

Architecture changes require updating

System Architecture

System Decisions

Project Manifest

before implementation.

---

# Rule 12

Scientific validity comes before optimization.

Never invent metrics without justification.

---

# Rule 13

Performance optimizations must never reduce correctness.

Correct

↓

Reliable

↓

Fast

Always.

---

# Rule 14

Keep modules independent.

Use well-defined interfaces.

Avoid hidden dependencies.

---

# Rule 15

Code should be understandable by another developer without explanation.

Readable code is preferred over clever code.