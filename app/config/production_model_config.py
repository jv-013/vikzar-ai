"""Versioned defaults for the permanent Phase 7 production model."""

from __future__ import annotations

PRODUCTION_MODEL_SCHEMA_VERSION = "1.0.0"
PRODUCTION_MODEL_ALGORITHM = "production.deterministic_mlp_regressor"
PRODUCTION_MODEL_MEDIA_TYPE = "application/vnd.vikzar.production-model+json"

DEFAULT_HIDDEN_LAYER_SIZES = (16, 8)
DEFAULT_LEARNING_RATE = 0.01
DEFAULT_EPOCHS = 400
DEFAULT_L2_PENALTY = 0.0001
DEFAULT_RANDOM_SEED = 137
DEFAULT_ADAM_BETA_ONE = 0.9
DEFAULT_ADAM_BETA_TWO = 0.999
DEFAULT_ADAM_EPSILON = 1e-8
