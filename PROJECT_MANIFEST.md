# PROJECT MANIFEST

## Purpose

This document is the single source of truth for Vikzar AI.

Every developer and every AI coding assistant (Codex, ChatGPT, etc.) must read this document before modifying the project.

Detailed information is available inside the `/docs` directory.

---

# Project

Vikzar AI

Real-Time Football Performance, Fatigue Monitoring, Muscle Activity Estimation and Injury Risk Prediction Platform.

---

# Mission

Build a production-grade AI platform capable of monitoring football athletes in real time using wearable sensors, biomechanics and machine learning.

---

# High-Level System

Training Mode

Smart Shin Pad

+

EMG Band

↓

Bluetooth BLE

↓

ETL

↓

FeatureVector

↓

AI Pipeline

↓

Cloud

---

Match Mode

Smart Shin Pad

↓

Bluetooth BLE

↓

ETL

↓

FeatureVector

↓

Muscle Activity Estimation

↓

AI

↓

Dashboard

↓

Cloud

---

# Repository Structure

app/

Production source code.

data/

Synthetic datasets, processed datasets and trained models.

docs/

Complete project documentation.

tests/

Unit, integration and performance tests.

scripts/

Utility scripts.

---

# Engineering Responsibilities

ETL Engineer

Owns

app/etl

Responsibilities

- BLE
- Packet Validation
- Synchronization
- Calibration
- Filtering
- Sliding Windows
- Feature Extraction
- Feature Validation

Output

FeatureVector

---

AI Engineer

Owns

- validation
- knowledge_base
- lookup_engine
- feature_enhancement
- benchmarking
- models
- inference
- risk_engine
- cloud
- api

Input

FeatureVector

Output

Predictions

Risk Scores

Vikzar Index

---

# Runtime Pipeline

Hardware

↓

BLE

↓

ETL

↓

FeatureVector

↓

Validation

↓

Knowledge Base

↓

Lookup Engine

↓

Muscle Activity Estimation

↓

Feature Enhancement

↓

Inference

↓

Risk Engine

↓

FastAPI

↓

Dashboard

↓

Cloud

---

# Core Rules

FeatureVector is immutable.

AI never performs ETL.

ETL never performs AI.

Cloud never blocks AI.

Dashboard never blocks AI.

Every module has exactly one responsibility.

All configuration belongs inside app/config.

No hardcoded values.

Use type hints everywhere.

Public functions require docstrings.

Every module requires tests.

---

# Performance Targets

Sampling Rate

100 Hz

FeatureVector Generation

100 milliseconds

AI Processing

<30 milliseconds

Cloud Upload

Asynchronous

---

# Design Principles

- Scientific validity
- Real-time processing
- Modular architecture
- Separation of concerns
- Hardware independence
- Cloud independence
- Production-ready engineering
- Scalable design

---

# Development Workflow

Research

↓

Design

↓

Documentation

↓

Implementation

↓

Unit Testing

↓

Integration Testing

↓

Benchmarking

↓

Production

---

# Documentation Index

Architecture

docs/architecture/

Development

docs/development/

Deployment

docs/deployment/

API

docs/api/

Research

docs/research/

---

# Git Workflow

Before coding

git pull

After coding

git add .

git commit

git push

---

# Future Goals

- Live football analytics
- Personalized injury prediction
- Team analytics
- Coach dashboard
- Cloud analytics
- Automated retraining
- Mobile application
- Multi-player support
- Professional club deployment

---

# Final Principle

Never violate the documented architecture.

When introducing new features, extend the architecture instead of bypassing it.

Maintain scientific validity, modularity and production-quality software at all times.