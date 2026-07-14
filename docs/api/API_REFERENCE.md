# API Reference

## Purpose

Defines the REST API exposed by Vikzar AI.

The API provides real-time predictions, player information, session management, and historical analytics.

---

# Base URL

/api/v1

---

# Authentication

Future versions will use:

- JWT
- OAuth2

Current development version does not require authentication.

---

# Endpoints

## Health

GET

/health

Returns

- Server Status
- AI Status
- ETL Status
- Cloud Status

---

## Player

GET

/player/{player_id}

Returns

Player Profile

---

POST

/player

Create Player

---

PUT

/player/{player_id}

Update Player

---

DELETE

/player/{player_id}

Delete Player

---

## Session

POST

/session/start

Start training or match session.

---

POST

/session/end

End current session.

---

GET

/session/{session_id}

Retrieve session information.

---

## Prediction

POST

/predict

Input

FeatureVector

Output

Prediction

Fatigue

Risk Score

Vikzar Index

---

## Dashboard

GET

/dashboard/live

Returns

Current live player metrics.

---

## Models

GET

/models

Available production models.

---

POST

/models/reload

Reload production model.

---

## Cloud

POST

/cloud/upload

Trigger manual upload.

---

GET

/cloud/status

Cloud health information.

---

# Response Format

Every API returns

status

message

timestamp

data

errors

---

# Future Endpoints

Analytics

Reports

Team Dashboard

Coach Dashboard

Admin Dashboard