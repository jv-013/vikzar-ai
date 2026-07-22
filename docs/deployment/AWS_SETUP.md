# AWS Setup

## Purpose

This document describes how Vikzar AI integrates with Amazon Web Services (AWS).

Cloud services are used for storage, analytics, monitoring, and future model management.

Cloud infrastructure is intentionally separated from the real-time AI pipeline.

Real-time prediction must never depend on cloud availability.

---

# AWS Services

The current architecture uses the following AWS services.

## Amazon S3

Purpose

- Store raw datasets
- Store processed datasets
- Store trained models
- Store logs
- Store exported reports

---

## Amazon DynamoDB

Purpose

- Player metadata
- Session metadata
- Live status
- Dashboard cache

---

## Amazon RDS (PostgreSQL)

Purpose

- Historical analytics
- Long-term player history
- Injury history
- Team statistics

---

## Amazon CloudWatch

Purpose

- Logs
- Runtime monitoring
- Error tracking
- Performance monitoring

---

## Amazon IAM

Purpose

Manage permissions for:

- ETL
- AI
- Dashboard
- Cloud Workers

---

## Future AWS Services

Potential future integrations

- SageMaker
- Lambda
- API Gateway
- SNS
- SQS

These are not required for the initial version.

---

# Upload Strategy

FeatureVector

↓

Upload Queue

↓

Cloud Worker

↓

AWS

Cloud uploads never block the AI pipeline.

---

# Security

AWS credentials should never be hardcoded.

Credentials must be loaded from:

- Environment Variables
- Secrets Manager
- Configuration Files

---

# Deployment Philosophy

Cloud enhances the system.

Cloud never controls the system.

Real-time inference always executes locally.