"""A real `BLETransport` (see `transport.py`) implementation using `bleak`
— the standard cross-platform Python BLE library (macOS/Linux/Windows).

**Untested against physical hardware.** No Universal Pod or EMG Band
exists in this development environment to connect to. This is real,
production-shaped code — real `bleak` GATT connect/notify/disconnect
calls, no simulated data — but it has never been exercised against an
actual device, and its two hardware-specific unknowns
(`address_by_device_id`, `notify_characteristic_uuid`) are supplied by
the caller rather than hardcoded, because this pipeline has no
provisioned Smart Pod/EMG Band GATT profile to hardcode: the actual
BLE address (or platform UUID) and notification characteristic UUID for
Vikzar's hardware are not known values anywhere in this repository. Per
`app.config.etl_config`'s own docstring, `SMART_POD_DEVICE_ID`/
`EMG_BAND_DEVICE_ID` ("smart_pod"/"emg_band") are *application*
identifiers, not BLE addresses — resolving one to the other is exactly
this transport's job, via the mapping supplied at construction.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from bleak import BleakClient
from bleak.exc import BleakError

from app.config.etl_config import (
    BLE_CONNECTION_TIMEOUT_SECONDS,
    BLE_RECONNECT_BACKOFF_SECONDS,
    BLE_RECONNECT_MAX_ATTEMPTS,
)

from .exceptions import BLEConnectionError, BLEDeviceNotFoundError
from .transport import DisconnectCallback, PacketCallback

logger = logging.getLogger(__name__)


class BleakBLETransport:
    """Satisfies the `BLETransport` protocol using real `bleak` GATT
    connections. Retry/backoff policy matches `app.config.etl_config`'s
    existing constants — the same policy `BLEReceiver` already assumes
    a transport will honor internally on `connect()`.
    """

    def __init__(
        self,
        *,
        address_by_device_id: Dict[str, str],
        notify_characteristic_uuid: str,
        connection_timeout_seconds: float = BLE_CONNECTION_TIMEOUT_SECONDS,
        max_connect_attempts: int = BLE_RECONNECT_MAX_ATTEMPTS,
        reconnect_backoff_seconds: float = BLE_RECONNECT_BACKOFF_SECONDS,
    ) -> None:
        self._address_by_device_id = dict(address_by_device_id)
        self._notify_characteristic_uuid = notify_characteristic_uuid
        self._connection_timeout_seconds = connection_timeout_seconds
        self._max_connect_attempts = max_connect_attempts
        self._reconnect_backoff_seconds = reconnect_backoff_seconds

        self._clients: Dict[str, BleakClient] = {}
        self._notification_handler: Optional[PacketCallback] = None
        self._disconnect_handler: Optional[DisconnectCallback] = None

    async def connect(self, device_id: str, timeout_seconds: float) -> None:
        address = self._address_by_device_id.get(device_id)
        if address is None:
            raise BLEDeviceNotFoundError(device_id)

        effective_timeout = min(timeout_seconds, self._connection_timeout_seconds)
        last_error: Exception | None = None
        for attempt in range(1, self._max_connect_attempts + 1):
            try:
                client = BleakClient(
                    address,
                    disconnected_callback=lambda _client, dev_id=device_id: (
                        self._handle_unexpected_disconnect(dev_id)
                    ),
                    timeout=effective_timeout,
                )
                await client.connect()
                await client.start_notify(
                    self._notify_characteristic_uuid,
                    lambda _handle, data, dev_id=device_id: self._handle_notification(
                        dev_id, bytes(data)
                    ),
                )
                self._clients[device_id] = client
                return
            except (BleakError, asyncio.TimeoutError, OSError) as exc:
                last_error = exc
                logger.warning(
                    "BLE connect attempt %d/%d failed for %s: %s",
                    attempt,
                    self._max_connect_attempts,
                    device_id,
                    exc,
                )
                if attempt < self._max_connect_attempts:
                    await asyncio.sleep(self._reconnect_backoff_seconds * attempt)

        raise BLEConnectionError(device_id) from last_error

    async def disconnect(self, device_id: str) -> None:
        client = self._clients.pop(device_id, None)
        if client is not None and client.is_connected:
            await client.disconnect()

    def is_connected(self, device_id: str) -> bool:
        client = self._clients.get(device_id)
        return client is not None and client.is_connected

    def set_notification_handler(self, handler: PacketCallback) -> None:
        self._notification_handler = handler

    def set_disconnect_handler(self, handler: DisconnectCallback) -> None:
        self._disconnect_handler = handler

    def _handle_notification(self, device_id: str, data: bytes) -> None:
        if self._notification_handler is not None:
            self._notification_handler(device_id, data)

    def _handle_unexpected_disconnect(self, device_id: str) -> None:
        self._clients.pop(device_id, None)
        if self._disconnect_handler is not None:
            self._disconnect_handler(device_id)
