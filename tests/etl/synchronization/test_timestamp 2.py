"""Unit tests for ReferenceTimestampResolver."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config import etl_config
from app.etl.synchronization.timestamp import ReferenceTimestampResolver


def test_first_packet_anchors_on_received_at() -> None:
    resolver = ReferenceTimestampResolver()
    received_at = datetime.fromtimestamp(12345.0 / 1000.0, tz=timezone.utc)

    reference_timestamp = resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=1000,
        sequence_number=1,
        received_at=received_at,
    )

    assert reference_timestamp == pytest.approx(12345.0)


def test_subsequent_packets_use_device_clock_offset() -> None:
    resolver = ReferenceTimestampResolver()
    received_at = datetime.fromtimestamp(1000.0 / 1000.0, tz=timezone.utc)
    resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=1000,
        sequence_number=1,
        received_at=received_at,
    )

    # A later packet's received_at is irrelevant to tier 1 resolution —
    # only the device-clock delta from the first packet matters.
    later_received_at = datetime.fromtimestamp(999999.0 / 1000.0, tz=timezone.utc)
    reference_timestamp = resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=1010,
        sequence_number=2,
        received_at=later_received_at,
    )

    assert reference_timestamp == pytest.approx(1010.0)


def test_devices_are_tracked_independently() -> None:
    resolver = ReferenceTimestampResolver()
    resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=1000,
        sequence_number=1,
        received_at=datetime.fromtimestamp(5000.0 / 1000.0, tz=timezone.utc),
    )
    resolver.resolve(
        device_id="right_smart_pod",
        device_timestamp_ms=1000,
        sequence_number=1,
        received_at=datetime.fromtimestamp(9000.0 / 1000.0, tz=timezone.utc),
    )

    left_next = resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=1010,
        sequence_number=2,
        received_at=datetime.fromtimestamp(5010.0 / 1000.0, tz=timezone.utc),
    )
    right_next = resolver.resolve(
        device_id="right_smart_pod",
        device_timestamp_ms=1010,
        sequence_number=2,
        received_at=datetime.fromtimestamp(9010.0 / 1000.0, tz=timezone.utc),
    )

    assert left_next == pytest.approx(5010.0)
    assert right_next == pytest.approx(9010.0)


def test_detected_clock_reset_falls_back_to_sequence_estimate() -> None:
    resolver = ReferenceTimestampResolver()
    resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=5000,
        sequence_number=100,
        received_at=datetime.fromtimestamp(2000.0 / 1000.0, tz=timezone.utc),
    )
    # Normal packet establishing last_reference_timestamp_ms = 2010,
    # last_sequence_number = 101.
    resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=5010,
        sequence_number=101,
        received_at=datetime.fromtimestamp(2010.0 / 1000.0, tz=timezone.utc),
    )

    # device_timestamp_ms drops sharply: a reboot. Sequence number
    # continues incrementing normally (device-side counter persists
    # differently from the clock, or simply continues from firmware
    # state) — estimate from the last known-good reference point.
    reference_timestamp = resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=50,  # reset, lower than previous 5010
        sequence_number=102,
        received_at=datetime.fromtimestamp(999999.0 / 1000.0, tz=timezone.utc),
    )

    expected = 2010.0 + (102 - 101) * etl_config.NOMINAL_SAMPLE_INTERVAL_MS
    assert reference_timestamp == pytest.approx(expected)


def test_resolution_resumes_normally_after_reset() -> None:
    resolver = ReferenceTimestampResolver()
    resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=5000,
        sequence_number=100,
        received_at=datetime.fromtimestamp(2000.0 / 1000.0, tz=timezone.utc),
    )
    reset_received_at = datetime.fromtimestamp(500000.0 / 1000.0, tz=timezone.utc)
    resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=50,
        sequence_number=101,
        received_at=reset_received_at,
    )

    # New offset is anchored at the reset packet's received_at. A
    # subsequent packet should use device-clock deltas from there.
    reference_timestamp = resolver.resolve(
        device_id="left_smart_pod",
        device_timestamp_ms=60,
        sequence_number=102,
        received_at=datetime.fromtimestamp(500020.0 / 1000.0, tz=timezone.utc),
    )

    assert reference_timestamp == pytest.approx(500010.0)
