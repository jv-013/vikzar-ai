"""
FeatureVector enrichment utilities.
"""

from app.schemas.feature_vector import FeatureVector

from .matchers import KnowledgeMatcher


class FeatureEnricher:
    """
    Enriches a FeatureVector with contextual
    knowledge retrieved from the Knowledge Base.
    """

    def __init__(self, matcher: KnowledgeMatcher):
        self.matcher = matcher

    def enrich(self, feature_vector: FeatureVector) -> FeatureVector:
        """
        Populate the Context section of the
        FeatureVector.
        """

        feature_vector.context.player_profile = (
            self.matcher.match_player_level(feature_vector)
        )

        feature_vector.context.position_profile = (
            self.matcher.match_position(feature_vector)
        )

        feature_vector.context.injury_profile = (
            self.matcher.match_injury(feature_vector)
        )

        return feature_vector