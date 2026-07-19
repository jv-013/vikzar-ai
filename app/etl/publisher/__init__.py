"""
Publisher package.

Stage 9 of the ETL pipeline, and the formal ETL -> AI boundary. See
docs/architecture/04_ETL_ARCHITECTURE.md and
docs/development/PUBLISHER_DESIGN.md.

RawFeatureVector (app.schemas.raw_feature_vector) is the only AI-facing
type any ETL module constructs — exclusively here.
"""

from .player_session_context import PlayerSessionContext
from .publisher import Publisher, RawFeatureVectorConsumer

__all__ = [
    "Publisher",
    "RawFeatureVectorConsumer",
    "PlayerSessionContext",
]
