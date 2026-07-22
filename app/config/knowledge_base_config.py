"""Configuration for the packaged Vikzar AI knowledge base."""

from pathlib import Path


KNOWLEDGE_BASE_SCHEMA_VERSION = "1.0.0"
KNOWLEDGE_BASE_DATA_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "knowledge_base" / "data"
)
PLAYER_PROFILES_FILENAME = "player_profiles.json"
POSITION_PROFILES_FILENAME = "position_profiles.json"
INJURY_PROFILES_FILENAME = "injury_profiles.json"
BIOMECHANICAL_REFERENCES_FILENAME = "biomechanical_references.json"
KNOWLEDGE_METADATA_FILENAME = "knowledge_metadata.json"
