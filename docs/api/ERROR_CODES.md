# Error Codes

## Purpose

Defines standardized error responses.

---

# Success

200

OK

---

201

Created

---

# Client Errors

400

Invalid Request

---

401

Unauthorized

---

403

Forbidden

---

404

Resource Not Found

---

409

Conflict

---

422

Validation Failed

---

# Server Errors

500

Internal Server Error

---

502

Bad Gateway

---

503

Service Unavailable

---

504

Gateway Timeout

---

# AI Errors

AI001

Model Not Loaded

AI002

Prediction Failed

AI003

Invalid FeatureVector

---

# ETL Errors

ETL001

BLE Disconnected

ETL002

Packet Validation Failed

ETL003

Synchronization Failed

ETL004

Filtering Failed

---

# Cloud Errors

CLOUD001

Upload Failed

CLOUD002

AWS Unavailable

---

# Dashboard Errors

UI001

WebSocket Lost

UI002

Rendering Failure

---

# Logging

Every error should contain

Timestamp

Module

Error Code

Description

Recommended Action