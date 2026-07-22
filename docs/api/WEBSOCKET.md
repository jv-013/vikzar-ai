# Live Dashboard Transport

Phase 10 intentionally exposes no local WebSocket route.

Firebase is the single live-dashboard synchronization layer. The laptop
computes validation, Phase 8 inference, and Phase 9 risk locally, then sends
only allowlisted aggregate summaries through the injected Firebase transport.
Raw packets, raw IMU, raw EMG, and feature vectors remain local.
