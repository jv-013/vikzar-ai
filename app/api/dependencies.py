"""Dependency-injection contracts and local immutable repositories."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.inference.contracts import InferencePrediction, InferenceRequest
from app.risk_engine.contracts import (
    PlayerRiskBaseline,
    RiskAssessment,
    RiskAssessmentRequest,
)

from .auth import Authenticator
from .configuration import APISettings
from .firebase import FirebaseTransport
from .session import SessionCheckpointStore


class InferenceGateway(Protocol):
    """Only the completed Phase 8 public operation."""

    def predict_batch(
        self,
        requests: tuple[InferenceRequest, ...],
    ) -> tuple[InferencePrediction, ...]:
        """Return Phase 8 predictions."""


class RiskGateway(Protocol):
    """Only the completed Phase 9 public operation."""

    def assess(self, request: RiskAssessmentRequest) -> RiskAssessment:
        """Return a Phase 9 risk assessment."""


class BaselineRepository(Protocol):
    """Local versioned player-baseline lookup."""

    def get(self, player_id: str) -> PlayerRiskBaseline | None:
        """Return an immutable player baseline."""


class InMemoryBaselineRepository:
    """Immutable in-process baseline index."""

    def __init__(self, baselines: tuple[PlayerRiskBaseline, ...]) -> None:
        if len({item.player_id for item in baselines}) != len(baselines):
            raise ValueError("Player baselines must have unique player IDs.")
        self._values = {item.player_id: item for item in baselines}

    def get(self, player_id: str) -> PlayerRiskBaseline | None:
        return self._values.get(player_id)

    @classmethod
    def from_json_file(cls, path: Path) -> "InMemoryBaselineRepository":
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError("Baseline file must contain a JSON array.")
        return cls(
            tuple(PlayerRiskBaseline.model_validate(value) for value in values)
        )


@dataclass(frozen=True)
class ApplicationDependencies:
    """All external and completed-phase dependencies for application bootstrap."""

    settings: APISettings
    inference_engine: InferenceGateway
    risk_engine: RiskGateway
    baseline_repository: BaselineRepository
    checkpoint_store: SessionCheckpointStore
    clock: Callable[[], datetime]
    authenticator: Authenticator | None = None
    firebase_transport: FirebaseTransport | None = None
