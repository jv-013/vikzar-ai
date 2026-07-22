"""A real `FirebaseTransport` (see `firebase.py`) that calls the deployed
HTTPS Callable Cloud Functions in `vikzar-app/functions/`
(BACKEND_SPECIFICATION.md §17/§21) over plain HTTPS.

**Deliberately does not use the `firebase-admin` SDK.** Admin SDK
credentials grant unrestricted Firestore/Storage access — giving them to
this pipeline would silently recreate the exact direct-write trust model
BACKEND_SPECIFICATION.md §0 explicitly rejects for a field-deployed
laptop. Instead, this authenticates as the narrow, revocable "ingestion
principal" Firebase Auth account (§3) using its own ID token, obtained by
exchanging a long-lived refresh token via the standard Identity Toolkit
REST endpoint — the same mechanism any Firebase client SDK uses to keep a
signed-in user's session alive, just without a UI. `httpx` is already a
project dependency; no new one is introduced.

**Not exercised against a real deployment.** The Cloud Functions this
calls are built and unit-tested (`vikzar-app/functions/`) but not
deployed — deploying requires the project owner's Firebase CLI access.
This class is real, production-shaped code, honestly untested against a
live endpoint until that happens.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .ingestion_contracts import IngestLiveTickPayload, SubmitAlertPayload

_TOKEN_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"
_TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS = 60


@dataclass(frozen=True)
class FirebaseCallableTransportConfig:
    """Non-secret shape; the actual `api_key`/`refresh_token` values must
    come from environment variables or a secret manager, never a
    committed file — see `from_environment()`."""

    project_id: str
    region: str
    api_key: str
    refresh_token: str
    request_timeout_seconds: float = 10.0

    @classmethod
    def from_environment(cls, environ: dict[str, str]) -> "FirebaseCallableTransportConfig | None":
        """Returns `None` (never raises) when required secrets are absent
        — matches this pipeline's existing convention of degrading to
        "Firebase disabled" rather than failing startup when optional
        cloud configuration is incomplete (`APISettings.firebase_enabled`
        defaults to `False` for the same reason)."""
        project_id = environ.get("VIKZAR_FIREBASE_PROJECT_ID")
        api_key = environ.get("VIKZAR_FIREBASE_API_KEY")
        refresh_token = environ.get("VIKZAR_FIREBASE_INGESTION_REFRESH_TOKEN")
        if not project_id or not api_key or not refresh_token:
            return None
        return cls(
            project_id=project_id,
            region=environ.get("VIKZAR_FIREBASE_FUNCTIONS_REGION", "us-central1"),
            api_key=api_key,
            refresh_token=refresh_token,
        )


class FirebaseCallableTransport:
    """Implements `firebase.FirebaseTransport` against real deployed
    Callable Cloud Functions."""

    def __init__(self, config: FirebaseCallableTransportConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.request_timeout_seconds)
        self._cached_id_token: str | None = None
        self._cached_id_token_expires_at: float = 0.0

    async def call_ingest_live_tick(self, payload: IngestLiveTickPayload) -> None:
        await self._call("ingestLiveTick", payload.to_wire())

    async def call_submit_alert(self, payload: SubmitAlertPayload) -> None:
        await self._call("submitAlert", payload.to_wire())

    async def health(self) -> bool:
        try:
            await self._id_token()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, function_name: str, data: dict[str, object]) -> None:
        token = await self._id_token()
        url = (
            f"https://{self._config.region}-{self._config.project_id}"
            f".cloudfunctions.net/{function_name}"
        )
        response = await self._client.post(
            url,
            json={"data": data},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            error = body["error"]
            raise RuntimeError(
                f"{function_name} failed: {error.get('status', 'UNKNOWN')} "
                f"— {error.get('message', 'no message')}"
            )

    async def _id_token(self) -> str:
        """Returns a cached, still-valid ID token, refreshing it from the
        long-lived refresh token when it's absent or close to expiry —
        the standard OAuth2/Identity-Platform refresh-token exchange, not
        a bespoke mechanism."""
        now = time.monotonic()
        if self._cached_id_token is not None and now < self._cached_id_token_expires_at:
            return self._cached_id_token

        response = await self._client.post(
            _TOKEN_REFRESH_URL,
            params={"key": self._config.api_key},
            data={"grant_type": "refresh_token", "refresh_token": self._config.refresh_token},
        )
        response.raise_for_status()
        body = response.json()
        id_token = body["id_token"]
        expires_in = float(body["expires_in"])

        self._cached_id_token = id_token
        self._cached_id_token_expires_at = now + expires_in - _TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS
        return id_token
