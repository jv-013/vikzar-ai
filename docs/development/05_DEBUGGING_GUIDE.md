# Debugging Guide

## Purpose

Defines the debugging workflow for Vikzar AI.

---

# Step 1

Reproduce the issue.

Never debug intermittent behaviour without reproducing it.

---

# Step 2

Identify affected module.

Possible modules

- BLE
- ETL
- Validation
- Lookup Engine
- AI
- Cloud
- Dashboard

---

# Step 3

Check logs.

Review

ETL.log

AI.log

Cloud.log

API.log

---

# Step 4

Verify inputs.

Confirm incoming FeatureVector is valid.

---

# Step 5

Test module independently.

Never debug the entire pipeline immediately.

---

# Step 6

Run unit tests.

---

# Step 7

Run integration tests.

---

# Common Issues

BLE disconnected

↓

Reconnect

---

Missing FeatureVector fields

↓

Validation error

---

Prediction failure

↓

Verify model loading

---

Cloud upload failure

↓

Queue stores pending uploads

Retry later

---

Dashboard failure

↓

Restart Dashboard only

Do not restart AI

---

# Logging Levels

DEBUG

Development

INFO

Normal runtime

WARNING

Recoverable issue

ERROR

Failure

CRITICAL

System cannot continue

---

# Debugging Principles

Reproduce

↓

Isolate

↓

Fix

↓

Test

↓

Deploy