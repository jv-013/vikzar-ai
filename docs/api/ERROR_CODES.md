# API Error Codes

Phase 10 returns a stable JSON `error` object containing `code`, `message`,
`correlation_id`, `timestamp`, and optional validation `details`.

- `API_INVALID_CORRELATION_ID` — 400
- `API_UNAUTHORIZED` — 401
- `SESSION_NOT_FOUND` — 404
- `SESSION_CONFLICT` — 409
- `SESSION_RECOVERY_FAILED` — 409
- `API_REQUEST_TOO_LARGE` — 413
- `API_VALIDATION_FAILED` — 422
- `PIPELINE_INPUT_REJECTED` — 422
- `API_INTERNAL_ERROR` — 500

Internal stack traces, secrets, tokens, feature values, and provider failure
details are never returned.
