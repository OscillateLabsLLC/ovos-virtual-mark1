import json

import pytest
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer

from ovos_virtual_mark1.app import Faceplate, build_parser
from ovos_virtual_mark1.bus import BusLink
from tests.conftest import wait_for


class FakeBus:
    """A websocket endpoint that records every message, like /core on the messagebus."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        self.app = web.Application()
        self.app.add_routes([web.get("/core", self._core)])

    async def _core(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            if msg.type is WSMsgType.TEXT:
                self.received.append(json.loads(msg.data))
        return ws


@pytest.fixture
async def fake_bus():
    bus = FakeBus()
    server = TestServer(bus.app)
    await server.start_server()
    try:
        yield bus, f"ws://127.0.0.1:{server.port}/core"
    finally:
        await server.close()


async def test_bus_link_connects_and_emits(fake_bus):
    bus, url = fake_bus
    link = BusLink(url)
    await link.start()
    try:
        await wait_for(lambda: link.connected)
        assert await link.emit("enclosure.mouth.text", {"text": "HI"})
        await wait_for(lambda: bus.received)
        assert bus.received[0]["type"] == "enclosure.mouth.text"
        assert bus.received[0]["data"] == {"text": "HI"}
        assert bus.received[0]["context"]["source"] == "ovos-virtual-mark1"
    finally:
        await link.stop()


async def test_bus_link_drops_when_disconnected():
    link = BusLink("ws://127.0.0.1:1/core")
    assert not link.connected
    assert await link.emit("speak", {}) is False


async def test_panel_events_publish_to_bus_and_inject_serial(fake_bus):
    bus, url = fake_bus
    faceplate = Faceplate(serial_port=0, http_port=0, bus_url=url)
    await faceplate.bus.start()
    try:
        await wait_for(lambda: faceplate.bus.connected)
        async with TestClient(TestServer(faceplate.web.app)) as http:
            ws = await http.ws_connect("/ws")
            first = await ws.receive_json()
            assert first["bus_connected"] is True
            await ws.send_json({"type": "bus", "msg_type": "enclosure.eyes.color", "data": {"r": 1, "g": 2, "b": 3}})
            await ws.send_json({"type": "bus", "data": {}})
            await ws.send_json({"type": "serial", "line": "mouth.text=DIRECT"})
            await wait_for(lambda: bus.received and faceplate.arduino.mouth.text == "DIRECT")
            assert bus.received == [
                {"type": "enclosure.eyes.color", "data": {"r": 1, "g": 2, "b": 3}, "context": {"source": "ovos-virtual-mark1"}}
            ]
            await ws.close()
    finally:
        await faceplate.bus.stop()


async def test_bus_event_without_bus_is_dropped():
    faceplate = Faceplate(serial_port=0, http_port=0, bus_url=None)
    assert faceplate.state()["bus_connected"] is False
    await faceplate.web.handle_input({"type": "bus", "msg_type": "speak", "data": {}})


def test_cli_bus_flags():
    assert build_parser().parse_args([]).bus == "ws://127.0.0.1:8181/core"
    assert build_parser().parse_args(["--no-bus"]).no_bus is True
    assert build_parser().parse_args(["--bus", "ws://host:1/core"]).bus == "ws://host:1/core"
