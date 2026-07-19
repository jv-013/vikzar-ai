"""
Test-only ValidatedPacket factory for Synchronization tests.

Not shipped production code — mirrors the role FakeBLETransport and the
VDPP test encoder play for earlier stages' tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Optional

from app.etl.validation.packet import ValidatedPacket


class FakeMonotonicClock:
    """A settable stand-in for time.monotonic(), for deterministic timeout tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance_ms(self, milliseconds: float) -> None:
        self._now += milliseconds / 1000.0


def make_validated_packet(
    device_id: str,
    reference_timestamp_ms: float,
    sequence_number: int = 0,
    raw_channels: Optional[Mapping[str, int]] = None,
) -> ValidatedPacket:
    """
    Construct a ValidatedPacket whose resolved reference_timestamp will
    be exactly `reference_timestamp_ms`.

    Achieved by setting received_at so that the per-device clock offset
    anchors at exactly zero: for a device_id used consistently with
    monotonically increasing reference_timestamp_ms values across a
    test, ReferenceTimestampResolver.resolve() returns
    device_timestamp_ms unchanged (offset never moves off zero), giving
    tests exact, predictable control over matching/timeout arithmetic.
    """
    received_at = datetime.fromtimestamp(reference_timestamp_ms / 1000.0, tz=timezone.utc)
    return ValidatedPacket(
        device_id=device_id,
        received_at=received_at,
        protocol_version=1,
        packet_type=1,
        sequence_number=sequence_number,
        device_timestamp_ms=int(reference_timestamp_ms),
        raw_channels=dict(raw_channels or {"x": 1}),
    )
