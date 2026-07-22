"""Authentication and secret-resolution interfaces with no provider coupling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .exceptions import AuthenticationError


class SecretProvider(Protocol):
    """Resolve a named secret without embedding it in application settings."""

    def get_secret(self, name: str) -> str | None:
        """Return a secret or None without logging its value."""


@dataclass(frozen=True)
class AuthPrincipal:
    """Minimal immutable identity made available to request handlers."""

    subject: str
    roles: tuple[str, ...] = ()


class Authenticator(Protocol):
    """Deployment-injected authentication provider."""

    async def authenticate(self, bearer_token: str) -> AuthPrincipal:
        """Validate one opaque bearer token or raise AuthenticationError."""


class AnonymousAuthenticator:
    """Explicit local/offline hook used only when authentication is disabled."""

    async def authenticate(self, bearer_token: str) -> AuthPrincipal:
        if bearer_token:
            raise AuthenticationError(
                "Bearer tokens are not accepted when anonymous mode is configured."
            )
        return AuthPrincipal(subject="anonymous")
