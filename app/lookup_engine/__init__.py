"""Immutable contextual retrieval for the Vikzar AI pipeline."""

from app.lookup_engine.engine import LookupEngine, get_lookup_engine
from app.lookup_engine.entities import (
    EvidenceContext,
    InjuryProfileContext,
    LookupResult,
    MetricDefinition,
    MetricProvenanceContext,
    PlayerProfileContext,
    PositionProfileContext,
    ScientificSourceContext,
)
from app.lookup_engine.exceptions import (
    InjuryKnowledgeNotFoundError,
    KnowledgeReferenceNotFoundError,
    LookupError,
    PositionKnowledgeNotFoundError,
)

__all__ = [
    "EvidenceContext",
    "InjuryKnowledgeNotFoundError",
    "InjuryProfileContext",
    "KnowledgeReferenceNotFoundError",
    "LookupEngine",
    "LookupError",
    "LookupResult",
    "MetricDefinition",
    "MetricProvenanceContext",
    "PlayerProfileContext",
    "PositionKnowledgeNotFoundError",
    "PositionProfileContext",
    "ScientificSourceContext",
    "get_lookup_engine",
]
