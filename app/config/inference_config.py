"""Versioned deterministic configuration defaults for Phase 8 inference."""

from __future__ import annotations

from app.config import dataset_builder_config, production_model_config

INFERENCE_SCHEMA_VERSION = "1.0.0"
SUPPORTED_PRODUCTION_MODEL_VERSIONS = (
    production_model_config.PRODUCTION_MODEL_SCHEMA_VERSION,
)
SUPPORTED_DATASET_SCHEMA_VERSIONS = (
    dataset_builder_config.DATASET_BUILDER_SCHEMA_VERSION,
)
SUPPORTED_INPUT_SCHEMA_VERSIONS = ("1.0.0",)
DEFAULT_MAX_BATCH_SIZE = 256
DEFAULT_MODEL_CACHE_SIZE = 4
