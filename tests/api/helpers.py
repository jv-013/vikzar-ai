"""Production-contract fakes and deterministic fixtures for Phase 10."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.auth import AuthPrincipal
from app.inference import InferenceMetadata, InferencePrediction, PredictionValue
from app.risk_engine import ACLRiskEngine
from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.group_feature_set import GroupFeatureSet
from app.schemas.hardware_provenance import HardwareProvenance
from app.schemas.player import Player
from app.schemas.quality_info import BiomarkerQualityInfo, QualityStatusInfo
from app.schemas.raw_feature_vector import RawFeatureVector
from app.schemas.session import Session
from tests.risk_engine.helpers import (
    HAMSTRING,
    LEFT_GROUP,
    QUADRICEPS,
    RIGHT_GROUP,
    TARGETS,
    make_baseline,
    make_config,
)


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 19, 16, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class ContractInferenceGateway:
    """Test gateway producing valid Phase 8 contracts and recording calls."""

    def __init__(self) -> None:
        self.calls = 0

    def predict_batch(self, requests):
        self.calls += 1
        results = []
        for request in requests:
            vector = request.feature_vector
            group = vector.groups[request.group_id]
            left = request.group_id == LEFT_GROUP
            values = (52.0, 31.0) if left else (51.0, 30.5)
            metadata = InferenceMetadata(
                model_id="production-model-001",
                model_version="1.0.0",
                model_checksum="a" * 64,
                model_configuration_hash="b" * 64,
                registration_id="production-registration-001",
                selection_id="production-selection-001",
                inference_configuration_hash="c" * 64,
                source_feature_vector_id=vector.feature_vector_id,
                source_schema_version=vector.schema_version,
                source_timestamp=vector.timestamp,
                player_id=vector.player.player_id,
                session_id=vector.session.session_id,
                group_id=request.group_id,
                window_start=group.window_start,
                window_end=group.window_end,
                feature_schema=(
                    "feature__motion__mean_angular_velocity",
                    "feature__motion__peak_resultant_acceleration",
                ),
                target_schema=TARGETS,
            )
            results.append(
                InferencePrediction.create(
                    predictions=(
                        PredictionValue(target_name=QUADRICEPS, value=values[0]),
                        PredictionValue(target_name=HAMSTRING, value=values[1]),
                    ),
                    metadata=metadata,
                )
            )
        return tuple(results)


class FakeFirebaseTransport:
    """Matches `app.api.firebase.FirebaseTransport` — one method per
    Callable Cloud Function, per the cross-repo contract alignment
    (DECISIONS.md ADR)."""

    def __init__(self, *, fail: bool = False, healthy: bool = True) -> None:
        self.fail = fail
        self.healthy = healthy
        self.live_ticks = []
        self.alerts = []
        self.closed = False

    async def call_ingest_live_tick(self, payload):
        if self.fail:
            raise RuntimeError("firebase unavailable")
        self.live_ticks.append(payload)

    async def call_submit_alert(self, payload):
        if self.fail:
            raise RuntimeError("firebase unavailable")
        self.alerts.append(payload)

    async def health(self):
        return self.healthy

    async def close(self):
        self.closed = True


class StaticAuthenticator:
    async def authenticate(self, bearer_token: str) -> AuthPrincipal:
        if bearer_token != "valid-token":
            raise ValueError("invalid")
        return AuthPrincipal(subject="operator-001", roles=("operator",))


def make_player() -> Player:
    return Player(
        player_id="player-001",
        age=24,
        sex="male",
        dominant_leg="right",
        position="midfielder",
    )


def make_session() -> Session:
    return Session(
        session_id="session-001",
        drill="cutting",
        training_intensity="moderate",
        fatigue_level=20,
    )


def make_raw_feature_vector(
    *,
    feature_vector_id: str = "feature-vector-001",
    window_start: float = 0,
    window_end: float = 1000,
) -> RawFeatureVector:
    quality = BiomarkerQualityInfo(
        status=QualityStatusInfo.VALID,
        flags=(),
        rationale="ETL accepted.",
    )
    domain = DomainBiomarkers(
        biomarkers={
            "mean_angular_velocity": 16.0,
            "peak_resultant_acceleration": 4.0,
        },
        quality={
            "mean_angular_velocity": quality,
            "peak_resultant_acceleration": quality,
        },
    )
    return RawFeatureVector(
        feature_vector_id=feature_vector_id,
        timestamp=datetime(2026, 7, 19, 14, tzinfo=timezone.utc),
        schema_version="1.0.0",
        source="vikzar_etl_v1",
        player=make_player(),
        session=make_session(),
        hardware=HardwareProvenance(
            firmware_revision="fw-1.0.0",
            hardware_revision="hw-v1",
            protocol_version="1",
        ),
        groups={
            LEFT_GROUP: GroupFeatureSet(
                window_start=window_start,
                window_end=window_end,
                motion=domain,
            ),
            RIGHT_GROUP: GroupFeatureSet(
                window_start=window_start,
                window_end=window_end,
                motion=domain,
            ),
        },
    )


def make_risk_engine() -> ACLRiskEngine:
    return ACLRiskEngine(make_config())


def default_baseline():
    return make_baseline()
