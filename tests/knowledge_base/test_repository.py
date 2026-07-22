"""Unit tests for the read-only knowledge-base repository."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from app.config.knowledge_base_config import KNOWLEDGE_BASE_DATA_DIRECTORY
from app.knowledge_base.exceptions import KnowledgeBaseDataError
from app.knowledge_base.repository import (
    KnowledgeBaseRepository,
    get_knowledge_base_repository,
)


class KnowledgeBaseRepositoryTests(unittest.TestCase):
    """Verify packaged knowledge is loaded and retrieved safely."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the production packaged knowledge once for the test class."""

        cls.repository = KnowledgeBaseRepository()

    def test_loads_position_profile_by_alias(self) -> None:
        """Position aliases resolve to the same immutable profile."""

        profile = self.repository.get_position_profile("Centre Forward")

        self.assertIsNotNone(profile)
        self.assertEqual(profile.position_key, "forward")

    def test_returns_none_for_unknown_player_without_fabricating_data(self) -> None:
        """Unknown players have no implicit or fabricated baseline profile."""

        self.assertIsNone(self.repository.get_player_profile("unknown-player"))

    def test_retrieves_ai_estimated_metric_with_measurable_basis(self) -> None:
        """Estimated metrics expose auditable measurable inputs."""

        reference = self.repository.get_biomechanical_reference(
            "muscles.left_right_activation_asymmetry"
        )

        self.assertIsNotNone(reference)
        self.assertEqual(reference.provenance.category, "ai_estimated")
        self.assertTrue(reference.provenance.measurable_feature_paths)

    def test_every_retrieved_reference_has_verifiable_sources(self) -> None:
        """Metrics must link to source records, not unstructured citation text."""

        reference = self.repository.get_biomechanical_reference(
            "derived.landing_stability"
        )

        self.assertIsNotNone(reference)
        self.assertTrue(reference.source_ids)
        for source_id in reference.source_ids:
            source = self.repository.get_scientific_source(source_id)
            self.assertIsNotNone(source)
            self.assertTrue(source.persistent_identifier)
            self.assertEqual(source.review_status, "reference_verified")

    def test_exposes_versioned_knowledge_metadata(self) -> None:
        """Loaded knowledge carries a verifiable version and source inventory."""

        metadata = self.repository.get_metadata()

        self.assertEqual(metadata.knowledge_version, "1.1.0")
        self.assertEqual(
            metadata.scientific_source_count,
            len(metadata.scientific_sources),
        )

    def test_shared_repository_is_loaded_once_per_process(self) -> None:
        """The dependency factory caches the validated startup snapshot."""

        self.assertIs(
            get_knowledge_base_repository(),
            get_knowledge_base_repository(),
        )

    def test_repository_data_directory_exists(self) -> None:
        """The packaged data directory remains part of the deployed module."""

        self.assertTrue(Path(KNOWLEDGE_BASE_DATA_DIRECTORY).is_dir())

    def test_fails_fast_when_required_knowledge_is_missing(self) -> None:
        """Startup cannot silently continue with partial scientific knowledge."""

        with TemporaryDirectory() as directory:
            with self.assertRaises(KnowledgeBaseDataError):
                KnowledgeBaseRepository(Path(directory))

    def test_returned_profiles_are_immutable(self) -> None:
        """Lookup callers cannot alter the repository's runtime knowledge."""

        profile = self.repository.get_position_profile("forward")

        self.assertIsNotNone(profile)
        with self.assertRaises((TypeError, ValidationError)):
            profile.display_name = "Modified"  # type: ignore[misc]
