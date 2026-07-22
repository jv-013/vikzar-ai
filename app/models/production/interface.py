"""Permanent interface implemented by Phase 7 production model adapters."""

from __future__ import annotations

from typing import Protocol

from app.experiments.contracts import MetadataValue
from app.experiments.runner import ModelAdapter


class ProductionModelAdapter(ModelAdapter, Protocol):
    """Phase 5 adapter plus immutable production training metadata."""

    @property
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return canonical production hyperparameters."""

    @property
    def random_seed(self) -> int:
        """Return the deterministic initialization seed."""
