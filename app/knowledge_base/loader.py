"""
Loads Knowledge Base JSON files into memory.
"""

import json
from pathlib import Path

from .entities import (
    BiomechanicsRule,
    InjuryProfile,
    PlayerProfile,
    PositionProfile,
)


class KnowledgeLoader:
    """
    Loads all knowledge files and converts them
    into strongly-typed entities.
    """

    def __init__(self, knowledge_directory: str):
        self.knowledge_directory = Path(knowledge_directory)

    def _load_json(self, filename: str):
        file_path = self.knowledge_directory / filename

        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def load_player_profiles(self):
        data = self._load_json("player_profiles.json")

        return {
            key: PlayerProfile(level=key, **value)
            for key, value in data.items()
        }

    def load_position_profiles(self):
        data = self._load_json("position_profiles.json")

        return {
            key: PositionProfile(position=key, **value)
            for key, value in data.items()
        }

    def load_injury_profiles(self):
        data = self._load_json("injury_profiles.json")

        return {
            key: InjuryProfile(
                injury_name=key,
                **value
            )
            for key, value in data.items()
        }

    def load_biomechanics_rules(self):
        data = self._load_json("biomechanics.json")

        return {
            key: BiomechanicsRule(
                name=key,
                **value
            )
            for key, value in data.items()
        }

    def load_all(self):
        return {
            "player_profiles": self.load_player_profiles(),
            "position_profiles": self.load_position_profiles(),
            "injury_profiles": self.load_injury_profiles(),
            "biomechanics": self.load_biomechanics_rules(),
        }