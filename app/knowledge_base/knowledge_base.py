"""
Main Knowledge Base interface.
"""

from .loader import KnowledgeLoader


class KnowledgeBase:
    """
    Central interface for accessing Vikzar's
    biomechanics knowledge.
    """

    def __init__(self, knowledge_directory: str):
        loader = KnowledgeLoader(knowledge_directory)
        self.knowledge = loader.load_all()

    def get_player_profile(self, position: str):
        return self.knowledge["player_profiles"].get(position)

    def get_injury_profile(self, injury: str):
        return self.knowledge["injury_profiles"].get(injury)

    def get_position_profile(self, position: str):
        return self.knowledge["position_profiles"].get(position)

    def get_biomechanics_rule(self, rule_name: str):
        return self.knowledge["biomechanics"].get(rule_name)