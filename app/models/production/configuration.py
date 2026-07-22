"""Immutable hyperparameter configuration for deterministic production training."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import production_model_config
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import MetadataValue


class ProductionModelConfig(BaseModel):
    """Complete deterministic training configuration for the production MLP."""

    model_config = ConfigDict(frozen=True)

    hidden_layer_sizes: tuple[int, ...] = Field(
        default=production_model_config.DEFAULT_HIDDEN_LAYER_SIZES,
        min_length=1,
        max_length=4,
    )
    learning_rate: float = Field(
        default=production_model_config.DEFAULT_LEARNING_RATE,
        gt=0,
        le=1,
    )
    epochs: int = Field(
        default=production_model_config.DEFAULT_EPOCHS,
        ge=1,
        le=10_000,
    )
    l2_penalty: float = Field(
        default=production_model_config.DEFAULT_L2_PENALTY,
        ge=0,
        le=1,
    )
    random_seed: int = production_model_config.DEFAULT_RANDOM_SEED
    adam_beta_one: float = Field(
        default=production_model_config.DEFAULT_ADAM_BETA_ONE,
        gt=0,
        lt=1,
    )
    adam_beta_two: float = Field(
        default=production_model_config.DEFAULT_ADAM_BETA_TWO,
        gt=0,
        lt=1,
    )
    adam_epsilon: float = Field(
        default=production_model_config.DEFAULT_ADAM_EPSILON,
        gt=0,
    )

    @field_validator("hidden_layer_sizes")
    @classmethod
    def validate_hidden_layers(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        """Bound permanent architecture dimensions to auditable sizes."""

        if any(value < 1 or value > 1024 for value in values):
            raise ValueError("Production hidden-layer sizes must be between 1 and 1024.")
        return values

    def metadata(self) -> tuple[MetadataValue, ...]:
        """Return canonical hyperparameters for the Phase 5 configuration hash."""

        return canonical_metadata(
            {
                "adam_beta_one": self.adam_beta_one,
                "adam_beta_two": self.adam_beta_two,
                "adam_epsilon": self.adam_epsilon,
                "epochs": self.epochs,
                "hidden_layer_sizes": ",".join(
                    str(value) for value in self.hidden_layer_sizes
                ),
                "l2_penalty": self.l2_penalty,
                "learning_rate": self.learning_rate,
                "normalization": "training_zscore",
                "optimizer": "full_batch_adam",
                "validation_selection": "lowest_mse_then_earliest_epoch",
            }
        )
