"""
Knowledge matching utilities.
"""

from app.knowledge_base.knowledge_base import KnowledgeBase
from app.schemas.feature_vector import FeatureVector


class KnowledgeMatcher:
    """
    Finds relevant knowledge for a FeatureVector.
    """

    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base

    def match_position(self, feature_vector: FeatureVector):
        return self.knowledge_base.get_position_profile(
            feature_vector.player.position
        )

    def match_injury(self, feature_vector: FeatureVector):
        return self.knowledge_base.get_injury_profile(
            feature_vector.player.injury_history
        )

    def match_player_level(self, feature_vector: FeatureVector):
        return self.knowledge_base.get_player_profile(
            feature_vector.player.fitness_level
        )