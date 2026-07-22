"""
PlayerSessionContext: static, session-level identity Publisher needs
but cannot derive from sensor data.

See docs/development/PUBLISHER_DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.player import Player
from app.schemas.session import Session


@dataclass(frozen=True)
class PlayerSessionContext:
    """
    Static identity and provenance for one ETL session, injected once at
    Publisher construction — never part of any handle() call, and never
    travels through the ETL pipeline itself.

    Purpose
        Player, session, and hardware/firmware/protocol identity are
        fixed facts about a session, not something derivable from a
        packet stream. Holding this as constructor-time configuration
        (the same pattern SynchronizationGroupConfig uses for
        Synchronizer) keeps every ETL stage before Publisher completely
        unaware that a "player" or "session" concept even exists.

    Attributes
        player: This session's player identity (app.schemas.Player).
        session: This session's identity (app.schemas.Session).
        firmware_revision: Smart Pod / EMG Band firmware revision
            active this session.
        hardware_revision: Physical hardware revision active this
            session.
        protocol_version: Wire protocol version active this session.
        schema_version: Stamped onto every published RawFeatureVector —
            the mechanism supporting future schema evolution without
            requiring old consumers to change.
        source: Static identifier for the system producing these
            records (e.g. "vikzar_etl_v1").

    Raises
        ValueError: If any string field is empty.
    """

    player: Player
    session: Session
    firmware_revision: str
    hardware_revision: str
    protocol_version: str
    schema_version: str
    source: str

    def __post_init__(self) -> None:
        for field_name in (
            "firmware_revision",
            "hardware_revision",
            "protocol_version",
            "schema_version",
            "source",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"PlayerSessionContext.{field_name} must not be empty.")
