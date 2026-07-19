"""
Exceptions raised by the BLE Receiver.
"""

from __future__ import annotations


class BLEReceiverError(Exception):
    """Base class for all BLE Receiver errors."""


class BLEDeviceNotFoundError(BLEReceiverError):
    """
    Raised when a transport cannot locate or reach a requested device.
    """

    def __init__(self, device_id: str) -> None:
        super().__init__(f"BLE device not found or unreachable: {device_id!r}")
        self.device_id = device_id


class BLEConnectionError(BLEReceiverError):
    """
    Raised when a device fails to connect after exhausting all configured
    retry attempts (see app.config.etl_config.BLE_RECONNECT_MAX_ATTEMPTS).
    """

    def __init__(self, device_id: str) -> None:
        super().__init__(
            f"Failed to connect to BLE device after exhausting retry attempts: {device_id!r}"
        )
        self.device_id = device_id
