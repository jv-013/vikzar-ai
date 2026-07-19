"""
ValidatedPacket: the internal contract between Packet Validation and
Synchronization.

ValidatedPacket is an ETL-internal type only, like RawPacket. It is not
part of the shared project schemas (app/schemas) and must never be
imported outside app/etl. It never crosses the ETL/AI boundary and has
no relationship to RawFeatureVector or EnhancedFeatureVector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ValidatedPacket:
    """
    A single structurally valid, decoded packet.

    Purpose
        Carry decoded raw sensor channel values — still uncalibrated,
        still in device-native units — from Packet Validation to
        Synchronization. Structural integrity is guaranteed here;
        scientific or physical plausibility is not evaluated at this
        stage.

    Attributes
        device_id: Logical source device, carried from RawPacket.
        received_at: Host reception timestamp, carried from RawPacket.
        protocol_version: The wire protocol version this packet was
            decoded as.
        packet_type: The packet type this packet was decoded as.
        sequence_number: Device-assigned sequence number, for
            packet-loss visibility. Not a substitute for received_at.
        device_timestamp_ms: Device-reported timestamp (milliseconds
            since device boot), not wall-clock time.
        raw_channels: Decoded raw numeric sensor channel values, keyed by
            channel name (e.g. "accel_x"). Uncalibrated, device-native
            units. The set of keys is decoder-specific.

    Raises
        ValueError: If device_id is empty or raw_channels is empty.
    """

    device_id: str
    received_at: datetime
    protocol_version: int
    packet_type: int
    sequence_number: int
    device_timestamp_ms: int
    raw_channels: Mapping[str, int]

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("ValidatedPacket.device_id must not be empty.")
        if not self.raw_channels:
            raise ValueError("ValidatedPacket.raw_channels must not be empty.")
        object.__setattr__(self, "raw_channels", MappingProxyType(dict(self.raw_channels)))
