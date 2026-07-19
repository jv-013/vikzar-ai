"""
RawPacket: the internal contract between BLE Receiver and Packet Validation.

RawPacket is an ETL-internal type only. It is not part of the shared
project schemas (app/schemas) and must never be imported outside app/etl.
It never crosses the ETL/AI boundary and has no relationship to
RawFeatureVector or EnhancedFeatureVector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RawPacket:
    """
    A single unparsed BLE notification captured by the BLE Receiver.

    Purpose
        Hand off exactly what was received over BLE, with no
        interpretation of its contents, to the next ETL stage.

    Attributes
        device_id: Logical identifier of the source device, as defined in
            app.config.etl_config (e.g. SMART_POD_DEVICE_ID).
        payload: Unparsed raw bytes exactly as received over BLE.
        received_at: UTC timestamp at which the BLE Receiver observed
            the notification.

    Raises
        ValueError: If device_id is empty.
        TypeError: If payload is not bytes.
    """

    device_id: str
    payload: bytes
    received_at: datetime

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("RawPacket.device_id must not be empty.")
        if not isinstance(self.payload, (bytes, bytearray)):
            raise TypeError("RawPacket.payload must be bytes.")
