"""Immutable environment-loadable configuration for Phase 10."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import api_integration_config


class APISettings(BaseModel):
    """Complete non-secret deployment configuration for the local compute node."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = api_integration_config.API_SCHEMA_VERSION
    application_name: str = "vikzar-ai"
    application_version: str = "1.0.0"
    environment: str = "production"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65_535)
    log_level: str = "INFO"
    auth_required: bool = True
    firebase_enabled: bool = False
    checkpoint_directory: Path = Path("./var/sessions")
    artifact_root: Path | None = None
    model_references_file: Path | None = None
    risk_policy_file: Path | None = None
    baselines_file: Path | None = None
    left_group_id: str = "left_lower_limb"
    right_group_id: str = "right_lower_limb"
    heartbeat_timeout_seconds: int = Field(
        default=api_integration_config.DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
        ge=1,
    )
    firebase_queue_capacity: int = Field(
        default=api_integration_config.DEFAULT_FIREBASE_QUEUE_CAPACITY,
        ge=1,
    )
    max_request_bytes: int = Field(
        default=api_integration_config.DEFAULT_MAX_REQUEST_BYTES,
        ge=1_024,
    )
    trusted_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")
    cors_origins: tuple[str, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != api_integration_config.API_SCHEMA_VERSION:
            raise ValueError("Unsupported API integration schema version.")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Unsupported structured logging level.")
        return normalized

    @field_validator("trusted_hosts", "cors_origins")
    @classmethod
    def validate_ordered_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if (
            any(not value.strip() for value in values)
            or len(set(values)) != len(values)
            or values != tuple(sorted(values))
        ):
            raise ValueError("Host and origin lists must be unique and ordered.")
        return values

    @model_validator(mode="after")
    def validate_security(self) -> "APISettings":
        if self.left_group_id == self.right_group_id:
            raise ValueError("Integration limb group IDs must differ.")
        if self.auth_required and "*" in self.cors_origins:
            raise ValueError("Authenticated deployments cannot allow wildcard CORS.")
        return self

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "APISettings":
        """Load explicit `VIKZAR_*` values without reading or logging secrets."""

        values = dict(os.environ if environ is None else environ)

        def optional_path(name: str) -> Path | None:
            value = values.get(name)
            return Path(value) if value else None

        def boolean(name: str, default: bool) -> bool:
            raw = values.get(name)
            if raw is None:
                return default
            normalized = raw.strip().lower()
            if normalized not in {"true", "false", "1", "0"}:
                raise ValueError(f"{name} must be a boolean.")
            return normalized in {"true", "1"}

        def csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
            raw = values.get(name)
            if raw is None:
                return default
            return tuple(sorted(item.strip() for item in raw.split(",") if item.strip()))

        return cls(
            application_name=values.get("VIKZAR_APP_NAME", "vikzar-ai"),
            application_version=values.get("VIKZAR_APP_VERSION", "1.0.0"),
            environment=values.get("VIKZAR_ENVIRONMENT", "production"),
            host=values.get("VIKZAR_HOST", "127.0.0.1"),
            port=int(values.get("VIKZAR_PORT", "8000")),
            log_level=values.get("VIKZAR_LOG_LEVEL", "INFO"),
            auth_required=boolean("VIKZAR_AUTH_REQUIRED", True),
            firebase_enabled=boolean("VIKZAR_FIREBASE_ENABLED", False),
            checkpoint_directory=Path(
                values.get("VIKZAR_CHECKPOINT_DIRECTORY", "./var/sessions")
            ),
            artifact_root=optional_path("VIKZAR_ARTIFACT_ROOT"),
            model_references_file=optional_path("VIKZAR_MODEL_REFERENCES_FILE"),
            risk_policy_file=optional_path("VIKZAR_RISK_POLICY_FILE"),
            baselines_file=optional_path("VIKZAR_BASELINES_FILE"),
            left_group_id=values.get("VIKZAR_LEFT_GROUP_ID", "left_lower_limb"),
            right_group_id=values.get("VIKZAR_RIGHT_GROUP_ID", "right_lower_limb"),
            heartbeat_timeout_seconds=int(
                values.get("VIKZAR_HEARTBEAT_TIMEOUT_SECONDS", "30")
            ),
            firebase_queue_capacity=int(
                values.get("VIKZAR_FIREBASE_QUEUE_CAPACITY", "1000")
            ),
            max_request_bytes=int(
                values.get("VIKZAR_MAX_REQUEST_BYTES", "1000000")
            ),
            trusted_hosts=csv(
                "VIKZAR_TRUSTED_HOSTS",
                ("127.0.0.1", "localhost", "testserver"),
            ),
            cors_origins=csv("VIKZAR_CORS_ORIGINS", ()),
        )
