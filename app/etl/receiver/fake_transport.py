"""
FakeBLETransport: a synthetic BLETransport implementation.

Requires no physical hardware. It satisfies the same BLETransport
interface a real hardware-backed implementation will satisfy later, so it
can be used both in unit tests and to run the ETL pipeline end-to-end
during local development before real hardware is available.

When real hardware becomes available, only a new transport implementation
needs to be written. BLEReceiver and every later ETL stage remain
unchanged, because they depend on BLETransport, never on this class.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, FrozenSet, Optional, Set

from .exceptions import BLEDeviceNotFoundError
from .transport import DisconnectCallback, PacketCallback

logger = logging.getLogger(__name__)


class FakeBLETransport:
    """
    In-memory BLETransport implementation for tests and local development.

    Purpose
        Let the ETL pipeline be developed and tested without physical
        hardware, and let development scripts simulate a live sensor
        stream via synthetic packets.

    Attributes
        known_device_ids: The set of logical device ids this fake transport
            can connect to. Connecting to any other id raises
            BLEDeviceNotFoundError.
        connect_failures: Optional mapping of device_id to the number of
            times connect() should fail with a transient ConnectionError
            before succeeding, for exercising BLEReceiver's retry logic.
    """

    def __init__(
        self,
        known_device_ids: FrozenSet[str],
        connect_failures: Optional[Dict[str, int]] = None,
    ) -> None:
        self._known_device_ids = known_device_ids
        self._connected: Set[str] = set()
        self._notification_handler: Optional[PacketCallback] = None
        self._disconnect_handler: Optional[DisconnectCallback] = None
        self._remaining_connect_failures: Dict[str, int] = dict(connect_failures or {})

    async def connect(self, device_id: str, timeout_seconds: float) -> None:
        """Simulate connecting to a device. See BLETransport.connect."""
        if device_id not in self._known_device_ids:
            raise BLEDeviceNotFoundError(device_id)

        remaining_failures = self._remaining_connect_failures.get(device_id, 0)
        if remaining_failures > 0:
            self._remaining_connect_failures[device_id] = remaining_failures - 1
            raise ConnectionError(f"Simulated connection failure for {device_id!r}.")

        self._connected.add(device_id)
        logger.info("fake_ble_transport.connected", extra={"device_id": device_id})

    async def disconnect(self, device_id: str) -> None:
        """Simulate disconnecting from a device. See BLETransport.disconnect."""
        self._connected.discard(device_id)
        logger.info("fake_ble_transport.disconnected", extra={"device_id": device_id})

    def is_connected(self, device_id: str) -> bool:
        """Return whether the given device is currently connected."""
        return device_id in self._connected

    def set_notification_handler(self, handler: PacketCallback) -> None:
        """Register the callback invoked by emit() for every packet."""
        self._notification_handler = handler

    def set_disconnect_handler(self, handler: DisconnectCallback) -> None:
        """Register the callback invoked by simulate_unexpected_disconnect()."""
        self._disconnect_handler = handler

    def emit(self, device_id: str, payload: bytes) -> None:
        """
        Synthetically emit a single packet, as if received over BLE.

        Args:
            device_id: The device the packet appears to originate from.
            payload: Raw bytes to deliver to the registered notification
                handler, unmodified.

        Raises:
            BLEDeviceNotFoundError: If device_id is not currently connected.
            RuntimeError: If no notification handler has been registered.
        """
        if device_id not in self._connected:
            raise BLEDeviceNotFoundError(device_id)
        if self._notification_handler is None:
            raise RuntimeError("FakeBLETransport has no notification handler registered.")
        self._notification_handler(device_id, payload)

    def set_connect_failures(self, device_id: str, count: int) -> None:
        """
        Configure how many subsequent connect() calls for device_id should
        fail with a transient ConnectionError before succeeding.

        Test-support helper, useful for reconfiguring failure behavior
        after an initial successful connect (e.g. to test reconnect
        failure without also failing the initial connection).
        """
        self._remaining_connect_failures[device_id] = count

    def simulate_unexpected_disconnect(self, device_id: str) -> None:
        """
        Simulate a device dropping its connection without disconnect()
        having been called, to exercise BLEReceiver's reconnect logic.
        """
        self._connected.discard(device_id)
        if self._disconnect_handler is not None:
            self._disconnect_handler(device_id)

    async def start_synthetic_stream(
        self,
        device_id: str,
        interval_seconds: float,
        payload_factory: Callable[[], bytes],
    ) -> None:
        """
        Continuously emit synthetic packets for local development.

        Not used by unit tests directly; intended for manually running
        the ETL pipeline end-to-end without physical hardware. Runs until
        the device is disconnected.

        Args:
            device_id: The device to emit packets for.
            interval_seconds: Delay between synthetic packets.
            payload_factory: Called to produce each packet's payload.
        """
        while self.is_connected(device_id):
            self.emit(device_id, payload_factory())
            await asyncio.sleep(interval_seconds)
