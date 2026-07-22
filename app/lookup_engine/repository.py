"""
Knowledge Repository.

Provides a single interface for retrieving
knowledge regardless of where it is stored.
"""

from app.knowledge_base.knowledge_base import KnowledgeBase


class KnowledgeRepository:

    def __init__(self, knowledge_directory: str):
        self.kb = KnowledgeBase(knowledge_directory)

    def get_position_profile(self, position: str):
        return self.kb.get_position_profile(position)

    def get_player_profile(self, level: str):
        return self.kb.get_player_profile(level)

    def get_injury_profile(self, injury: str):
        return self.kb.get_injury_profile(injury)

    def get_biomechanics_rule(self, rule: str):
        return self.kb.get_biomechanics_rule(rule)