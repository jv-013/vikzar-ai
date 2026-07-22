"""
Biomechanics and domain knowledge rules.
"""

from dataclasses import dataclass
from typing import Callable

from app.schemas.feature_vector import FeatureVector


@dataclass(frozen=True)
class KnowledgeRule:
    """
    Represents a biomechanics knowledge rule.
    """

    name: str
    description: str
    evaluator: Callable[[FeatureVector], bool]


# Example rules

HIGH_INTENSITY_MOVEMENT = KnowledgeRule(
    name="high_intensity_movement",
    description="Detects high-intensity movement.",
    evaluator=lambda fv: fv.derived.movement_intensity > 80
)


LOW_SYMMETRY = KnowledgeRule(
    name="low_symmetry",
    description="Detects low movement symmetry.",
    evaluator=lambda fv: fv.symmetry.overall_symmetry_score < 80
)


HIGH_FATIGUE = KnowledgeRule(
    name="high_fatigue",
    description="Detects high estimated muscle fatigue.",
    evaluator=lambda fv: fv.muscles.estimated_muscle_fatigue > 70
)