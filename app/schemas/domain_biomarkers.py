"""Lossless biomarker and ETL-quality payloads for one feature domain."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from app.schemas.quality_info import BiomarkerQualityInfo


class DomainBiomarkers(BaseModel):
    """Named ETL biomarker values and their matching quality annotations."""

    biomarkers: dict[str, float]
    quality: dict[str, BiomarkerQualityInfo]

    @model_validator(mode="after")
    def validate_quality_keys(self) -> "DomainBiomarkers":
        """Require one ETL quality annotation for every carried biomarker."""

        if set(self.biomarkers) != set(self.quality):
            raise ValueError(
                "Domain biomarker names must exactly match quality annotation names."
            )
        return self
