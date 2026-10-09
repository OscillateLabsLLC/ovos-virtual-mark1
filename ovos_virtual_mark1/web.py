"""HTTP and websocket server that streams faceplate state to the browser GUI."""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from aiohttp import WSMsgType, web

from ovos_virtual_mark1.arduino import VirtualArduino

LOG = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
StateProvider = Callable[[], dict]


class WebServer:
    def __init__(self, state: StateProvider, arduino: VirtualArduino, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.state = state
        self.arduino = arduino
        self.host = host
        self.port = port
        self._sockets: set[web.WebSocketResponse] = set()
        self._last_payload = ""
        self._runner: web.AppRunner | None = None
        self.app = web.Application()
        self.app.add_routes([web.get("/", self._index), web.get("/state", self._state), web.get("/ws", self._websocket)])
        self.app.router.add_static("/static/", STATIC_DIR)

    async def start(self) -> None:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        LOG.info("faceplate GUI at http://%s:%d/", self.host, self.port)

    async def stop(self) -> None:
        for ws in list(self._sockets):
            await ws.close()
        if self._runner:
            await self._runner.cleanup()

    async def broadcast_if_changed(self) -> None:
        payload = json.dumps(self.state(), separators=(",", ":"))
        if payload == self._last_payload:
            return
        self._last_payload = payload
        for ws in list(self._sockets):
            try:
                await ws.send_str(payload)
            except ConnectionError:
                self._sockets.discard(ws)

    async def _index(self, _request: web.Request) -> web.StreamResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    async def _state(self, _request: web.Request) -> web.Response:
        return web.json_response(self.state())

    async def _websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._sockets.add(ws)
        await ws.send_json(self.state())
        try:
            async for msg in ws:
                if msg.type is WSMsgType.TEXT:
                    self.handle_input(json.loads(msg.data))
        finally:
            self._sockets.discard(ws)
        return ws

    def handle_input(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "button":
            self.arduino.press_button()
        elif kind == "knob":
            self.arduino.turn_knob(clockwise=event.get("direction") == "up")
        else:
            LOG.warning("unknown GUI event %r", event)
