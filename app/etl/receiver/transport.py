"""
BLETransport: the abstraction the BLE Receiver depends on exclusively.

BLEReceiver never imports or depends on a concrete BLE library. It depends
only on this interface. This is what allows:

- Unit testing with FakeBLETransport, no hardware required.
- Synthetic packet generation during local development.
- Replacing this interface with a real hardware-backed implementation
  later without changing BLEReceiver or any other ETL stage.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

PacketCallback = Callable[[str, bytes], None]
"""Invoked by a BLETransport for every received notification: (device_id, payload)."""

DisconnectCallback = Callable[[str], None]
"""Invoked by a BLETransport when a device disconnects unexpectedly: (device_id)."""


@runtime_checkable
class BLETransport(Protocol):
    """
    Abstract BLE transport used by BLEReceiver.

    Any implementation — synthetic or hardware-backed — must satisfy this
    interface. Resolving a logical device id to actual BLE addressing or
    GATT characteristics is the responsibility of the implementation, not
    the receiver.
    """

    async def connect(self, device_id: str, timeout_seconds: float) -> None:
        """
        Establish a BLE connection to the given logical device.

        Args:
            device_id: Logical device identifier (see app.config.etl_config).
            timeout_seconds: Maximum time to wait for the connection.

        Raises:
            Exception: Any implementation-specific error on failure to
                connect within the timeout. BLEReceiver treats every
                exception raised here as a single failed attempt.
        """
        ...

    async def disconnect(self, device_id: str) -> None:
        """Terminate the BLE connection to the given logical device."""
        ...

    def is_connected(self, device_id: str) -> bool:
        """Return whether the given device is currently connected."""
        ...

    def set_notification_handler(self, handler: PacketCallback) -> None:
        """Register the callback invoked for every received notification."""
        ...

    def set_disconnect_handler(self, handler: DisconnectCallback) -> None:
        """Register the callback invoked when a device unexpectedly disconnects."""
        ...
