"""Raw, ETL-owned feature data for one synchronization group."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.quality_info import SetQualityObservationInfo


class GroupFeatureSet(BaseModel):
    """Lossless ETL output for one group and one feature window."""

    window_start: float
    window_end: float
    motion: DomainBiomarkers | None = None
    pressure: DomainBiomarkers | None = None
    muscle: DomainBiomarkers | None = None
    set_observations: tuple[SetQualityObservationInfo, ...] = ()

    @model_validator(mode="after")
    def validate_window_order(self) -> "GroupFeatureSet":
        """Reject a group feature window whose end does not follow its start."""

        if self.window_start >= self.window_end:
            raise ValueError("GroupFeatureSet.window_start must precede window_end.")
        return self
