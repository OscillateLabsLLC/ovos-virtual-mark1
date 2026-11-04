"""Minimal OVOS messagebus client so the GUI can publish messages for the real plugin to act on."""

import asyncio
import json
import logging

import aiohttp

LOG = logging.getLogger(__name__)
DEFAULT_BUS_URL = "ws://127.0.0.1:8181/core"
RECONNECT_DELAY_S = 3.0


class BusLink:
    """Keeps one websocket to the messagebus open and reconnects when it drops."""

    def __init__(self, url: str = DEFAULT_BUS_URL) -> None:
        self.url = url
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        self._task = asyncio.create_task(self._keep_connected())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()

    async def emit(self, msg_type: str, data: dict | None = None) -> bool:
        if not self.connected:
            LOG.warning("bus not connected; dropping %s", msg_type)
            return False
        payload = {"type": msg_type, "data": data or {}, "context": {"source": "ovos-virtual-mark1"}}
        await self._ws.send_str(json.dumps(payload))
        return True

    async def _keep_connected(self) -> None:
        while True:
            try:
                await self._hold_connection()
            except (aiohttp.ClientError, OSError) as err:
                LOG.debug("bus unavailable at %s: %s", self.url, err)
            self._ws = None
            await asyncio.sleep(RECONNECT_DELAY_S)

    async def _hold_connection(self) -> None:
        async with self._session.ws_connect(self.url, heartbeat=30) as ws:
            self._ws = ws
            LOG.info("connected to messagebus at %s", self.url)
            async for _ in ws:
                pass
            LOG.info("messagebus connection closed")
