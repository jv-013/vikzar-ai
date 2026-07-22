"""Immutable runtime configuration for deterministic production inference."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import inference_config


class InferenceRuntimeConfig(BaseModel):
    """Complete version and resource policy for one inference engine."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = inference_config.INFERENCE_SCHEMA_VERSION
    supported_model_versions: tuple[str, ...] = (
        inference_config.SUPPORTED_PRODUCTION_MODEL_VERSIONS
    )
    supported_dataset_versions: tuple[str, ...] = (
        inference_config.SUPPORTED_DATASET_SCHEMA_VERSIONS
    )
    supported_input_versions: tuple[str, ...] = (
        inference_config.SUPPORTED_INPUT_SCHEMA_VERSIONS
    )
    max_batch_size: int = Field(
        default=inference_config.DEFAULT_MAX_BATCH_SIZE,
        ge=1,
        le=100_000,
    )
    model_cache_size: int = Field(
        default=inference_config.DEFAULT_MODEL_CACHE_SIZE,
        ge=1,
        le=128,
    )

    @field_validator(
        "supported_model_versions",
        "supported_dataset_versions",
        "supported_input_versions",
    )
    @classmethod
    def validate_versions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require a canonical, non-empty set of supported schema versions."""

        if (
            not values
            or any(not value.strip() for value in values)
            or len(set(values)) != len(values)
            or values != tuple(sorted(values))
        ):
            raise ValueError(
                "Supported inference schema versions must be unique and ordered."
            )
        return values

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Prevent a runtime from claiming an unsupported Phase 8 contract."""

        if value != inference_config.INFERENCE_SCHEMA_VERSION:
            raise ValueError("Unsupported inference runtime schema version.")
        return value

    @property
    def configuration_hash(self) -> str:
        """Return the stable identity of this complete runtime configuration."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
