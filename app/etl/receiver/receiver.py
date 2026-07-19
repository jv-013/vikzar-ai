"""
BLE Receiver.

Stage 1 of the ETL pipeline (see docs/architecture/04_ETL_ARCHITECTURE.md).

Connects to configured BLE devices via a BLETransport, wraps every
incoming notification into a RawPacket, and forwards it to a downstream
consumer. Performs no packet interpretation, validation, or
synchronization — those are the responsibilities of later ETL stages.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, Set

from app.config import etl_config

from .exceptions import BLEConnectionError
from .packet import RawPacket
from .transport import BLETransport

logger = logging.getLogger(__name__)

PacketConsumer = Callable[[RawPacket], None]
"""Invoked by BLEReceiver with each RawPacket as it arrives."""


class BLEReceiver:
    """
    Receives raw BLE packets and forwards them as RawPacket instances.

    Purpose
        Establish and maintain BLE connections to the devices required for
        the current session, and hand off every received notification —
        unparsed — to a downstream consumer (Packet Validation).

    The receiver depends only on the BLETransport interface. It never
    interprets, validates, or synchronizes packet contents.
    """

    def __init__(self, transport: BLETransport, on_packet: PacketConsumer) -> None:
        """
        Initialize the receiver.

        Args:
            transport: BLE transport implementation (real or fake). The
                receiver depends only on the BLETransport interface.
            on_packet: Callback invoked with each RawPacket as it arrives.
        """
        self._transport = transport
        self._on_packet = on_packet
        self._active_device_ids: Set[str] = set()
        self._pending_reconnects: Dict[str, asyncio.Task] = {}
        self._started = False

        self._transport.set_notification_handler(self._handle_notification)
        self._transport.set_disconnect_handler(self._handle_unexpected_disconnect)

    async def start(self, device_ids: Iterable[str]) -> None:
        """
        Connect to the given devices and begin receiving packets.

        Args:
            device_ids: Logical device identifiers to connect to for this
                session, e.g. [etl_config.SMART_POD_DEVICE_ID] in Match
                Mode, or both SMART_POD_DEVICE_ID and EMG_BAND_DEVICE_ID in
                Training Mode.

        Raises:
            BLEConnectionError: If any device fails to connect after
                exhausting all configured retry attempts. Devices already
                connected before the failure remain connected.
        """
        for device_id in device_ids:
            await self._connect_with_retry(device_id)
            self._active_device_ids.add(device_id)

        self._started = True
        logger.info(
            "ble_receiver.started",
            extra={"device_ids": sorted(self._active_device_ids)},
        )

    async def stop(self) -> None:
        """
        Disconnect from all currently active devices.

        Cancels and awaits any in-flight reconnection attempts first, so
        stop() fully quiesces the receiver: no reconnect triggered by an
        earlier unexpected disconnect can complete or mutate state after
        this method returns.
        """
        await self._cancel_pending_reconnects()

        for device_id in list(self._active_device_ids):
            await self._transport.disconnect(device_id)
            self._active_device_ids.discard(device_id)

        self._started = False
        logger.info("ble_receiver.stopped")

    def is_running(self) -> bool:
        """Return whether the receiver has been started and not yet stopped."""
        return self._started

    def is_device_connected(self, device_id: str) -> bool:
        """Return whether the given device is currently connected."""
        return self._transport.is_connected(device_id)

    async def wait_for_pending_reconnects(self) -> None:
        """
        Await any in-flight reconnection attempts triggered by an
        unexpected disconnect.

        Primarily useful for tests and for graceful shutdown, since
        reconnection after an unexpected disconnect runs as a background
        task rather than blocking the caller.
        """
        if not self._pending_reconnects:
            return
        tasks = list(self._pending_reconnects.values())
        self._pending_reconnects.clear()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _cancel_pending_reconnects(self) -> None:
        """Cancel and await any in-flight reconnection attempts."""
        if not self._pending_reconnects:
            return
        tasks = list(self._pending_reconnects.values())
        self._pending_reconnects.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect_with_retry(self, device_id: str) -> None:
        attempts = 0
        last_error: Exception | None = None

        while attempts < etl_config.BLE_RECONNECT_MAX_ATTEMPTS:
            try:
                await self._transport.connect(
                    device_id, etl_config.BLE_CONNECTION_TIMEOUT_SECONDS
                )
                return
            except Exception as exc:
                attempts += 1
                last_error = exc
                logger.warning(
                    "ble_receiver.connect_attempt_failed",
                    extra={
                        "device_id": device_id,
                        "attempt": attempts,
                        "max_attempts": etl_config.BLE_RECONNECT_MAX_ATTEMPTS,
                        "error": str(exc),
                    },
                )
                if attempts < etl_config.BLE_RECONNECT_MAX_ATTEMPTS:
                    await asyncio.sleep(etl_config.BLE_RECONNECT_BACKOFF_SECONDS)

        logger.error(
            "ble_receiver.connect_exhausted",
            extra={"device_id": device_id, "attempts": attempts},
        )
        raise BLEConnectionError(device_id) from last_error

    def _handle_notification(self, device_id: str, payload: bytes) -> None:
        packet = RawPacket(
            device_id=device_id,
            payload=payload,
            received_at=datetime.now(timezone.utc),
        )
        logger.debug(
            "ble_receiver.packet_received",
            extra={"device_id": device_id, "payload_size": len(payload)},
        )
        self._on_packet(packet)

    def _handle_unexpected_disconnect(self, device_id: str) -> None:
        self._active_device_ids.discard(device_id)

        existing_task = self._pending_reconnects.get(device_id)
        if existing_task is not None and not existing_task.done():
            logger.warning(
                "ble_receiver.unexpected_disconnect_reconnect_already_in_progress",
                extra={"device_id": device_id},
            )
            return

        logger.warning("ble_receiver.unexpected_disconnect", extra={"device_id": device_id})
        self._pending_reconnects[device_id] = asyncio.ensure_future(self._reconnect(device_id))

    async def _reconnect(self, device_id: str) -> None:
        try:
            await self._connect_with_retry(device_id)
            self._active_device_ids.add(device_id)
            logger.info("ble_receiver.reconnected", extra={"device_id": device_id})
        except BLEConnectionError:
            logger.error("ble_receiver.reconnect_failed", extra={"device_id": device_id})
