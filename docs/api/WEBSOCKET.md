# WebSocket

## Purpose

Defines the real-time communication channel between Vikzar AI and the dashboard.

---

# Endpoint

/ws

---

# Purpose

Push live predictions.

Avoid continuous polling.

Reduce latency.

---

# Messages

Incoming

FeatureVector

Outgoing

Prediction

Risk

Fatigue

Vikzar Index

Alerts

---

# Update Frequency

Every FeatureVector

100 milliseconds.

---

# Connection

Dashboard

↓

WebSocket

↓

FastAPI

↓

AI

---

# Events

Connected

Disconnected

Prediction

Alert

Error

Heartbeat

---

# Reconnection

Automatically reconnect.

Maximum retries configurable.

---

# Future

Support multiple players simultaneously.

Support coach dashboard.

Support team analytics.