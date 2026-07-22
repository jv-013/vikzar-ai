"""The locked, ETL-owned runtime contract entering the AI pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.group_feature_set import GroupFeatureSet
from app.schemas.hardware_provenance import HardwareProvenance
from app.schemas.player import Player
from app.schemas.session import Session


class RawFeatureVector(BaseModel):
    """Lossless Publisher output at the ETL-to-AI trust boundary.

    This contract preserves ETL-owned groups, biomarker values, quality
    annotations, and provenance. AI modules must not modify its contents.
    """

    feature_vector_id: str
    timestamp: datetime
    schema_version: str
    source: str
    player: Player
    session: Session
    hardware: HardwareProvenance
    groups: dict[str, GroupFeatureSet]

    @field_validator("groups")
    @classmethod
    def validate_groups(cls, value: dict[str, GroupFeatureSet]) -> dict[str, GroupFeatureSet]:
        """Require at least one named synchronization group."""

        if not value:
            raise ValueError("RawFeatureVector.groups must not be empty.")
        if any(not group_id.strip() for group_id in value):
            raise ValueError("RawFeatureVector group identifiers must not be blank.")
        return value
