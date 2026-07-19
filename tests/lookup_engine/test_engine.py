"""Unit tests for read-only Lookup Engine contextual retrieval."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.knowledge_base.entities import PositionProfile
from app.knowledge_base.repository import KnowledgeBaseRepository
from app.lookup_engine.engine import LookupEngine, get_lookup_engine
from app.lookup_engine.entities import LookupResult, PositionProfileContext
from app.lookup_engine.exceptions import (
    InjuryKnowledgeNotFoundError,
    PositionKnowledgeNotFoundError,
)
from app.schemas.feature_vector import FeatureVector


class LookupEngineTests(unittest.TestCase):
    """Verify retrieval-only behavior over the production Knowledge Base."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create one injected engine using the production read-only repository."""

        cls.engine = LookupEngine(KnowledgeBaseRepository())

    def test_returns_lookup_engine_owned_immutable_context(self) -> None:
        """The engine returns DTOs rather than Knowledge Base entity instances."""

        result = self.engine.lookup(_feature_vector(position="forward"))

        self.assertIsInstance(result, LookupResult)
        self.assertIsInstance(result.position_profile, PositionProfileContext)
        self.assertNotIsInstance(result.position_profile, PositionProfile)
        self.assertTrue(result.metric_context)
        self.assertTrue(result.scientific_sources)
        self.assertEqual(
            result.metric_context[0].name,
            "imu.resultant_acceleration",
        )
        self.assertIsNone(result.metric_context[0].units)

    def test_injury_context_is_retrieved_without_inference(self) -> None:
        """Configured injury context is returned only when explicitly supplied."""

        result = self.engine.lookup(
            _feature_vector(
                position="forward",
                injury_history="hamstring strain",
            )
        )

        self.assertEqual(result.injury_profiles[0].injury_key, "hamstring_strain_history")
        metric_names = {metric.name for metric in result.metric_context}
        self.assertIn("emg.hamstring_quadriceps_ratio", metric_names)

    def test_unknown_position_fails_fast(self) -> None:
        """Unconfigured position input cannot produce partial contextual output."""

        with self.assertRaises(PositionKnowledgeNotFoundError):
            self.engine.lookup(_feature_vector(position="unsupported_position"))

    def test_unknown_supplied_injury_context_fails_fast(self) -> None:
        """Unconfigured injury input cannot be silently ignored or inferred."""

        with self.assertRaises(InjuryKnowledgeNotFoundError):
            self.engine.lookup(
                _feature_vector(
                    position="forward",
                    injury_status="unconfigured injury",
                )
            )

    def test_does_not_modify_feature_vector(self) -> None:
        """Lookup preserves the ETL-owned feature vector object and values."""

        feature_vector = _feature_vector(position="forward")
        original_player = feature_vector.player
        original_context = feature_vector.context

        self.engine.lookup(feature_vector)

        self.assertIs(feature_vector.player, original_player)
        self.assertIs(feature_vector.context, original_context)
        self.assertEqual(feature_vector.player.position, "forward")

    def test_shared_engine_is_cached_for_startup_use(self) -> None:
        """The application factory avoids reloading knowledge per request."""

        self.assertIs(get_lookup_engine(), get_lookup_engine())


def _feature_vector(
    *,
    position: str,
    injury_history: str | None = None,
    injury_status: str | None = None,
) -> FeatureVector:
    """Construct the minimal validated-upstream shape required by Lookup Engine tests."""

    field_values = {
        "metadata": SimpleNamespace(feature_vector_id="feature-vector-001"),
        "player": SimpleNamespace(
            player_id="player-001",
            position=position,
            injury_history=injury_history,
            injury_status=injury_status,
        ),
        "context": SimpleNamespace(),
    }
    if hasattr(FeatureVector, "model_construct"):
        return FeatureVector.model_construct(**field_values)
    return FeatureVector.construct(**field_values)
