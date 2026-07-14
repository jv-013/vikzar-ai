# Repository Structure

## Purpose

Defines the responsibility of every directory inside the Vikzar AI repository.

---

# Root Structure

```
vikzar-ai/

app/
data/
docs/
notebooks/
scripts/
tests/

README.md
requirements.txt
main.py
```

---

# app/

Contains all production source code.

---

## config/

Application configuration.

Contains:

• constants

• ETL configuration

• ML configuration

• Cloud configuration

• API configuration

---

## schemas/

Shared contracts between ETL and AI.

These files define the FeatureVector and all related data models.

Neither ETL nor AI should change schemas without agreement.

---

## etl/

Owned by ETL engineer.

Responsibilities:

• BLE

• Filtering

• Calibration

• Synchronization

• Feature Extraction

Output:

FeatureVector

---

## validation/

Validates FeatureVectors before AI processing.

---

## knowledge_base/

Stores biomechanical knowledge used by Lookup Engine.

---

## lookup_engine/

Enriches FeatureVectors using Knowledge Base.

---

## feature_enhancement/

Generates advanced AI features.

---

## benchmarking/

Training and model comparison.

---

## models/

Machine learning models.

---

## inference/

Real-time prediction.

---

## risk_engine/

Produces injury risk and Vikzar Index.

---

## cloud/

Cloud integration.

---

## api/

FastAPI backend.

---

## services/

Long-running background services.

---

## utils/

Shared helper functions.

---

# Ownership

ETL Engineer

app/etl

AI Engineer

Everything else.