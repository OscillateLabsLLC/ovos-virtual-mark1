import asyncio

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ovos_virtual_mark1.app import Faceplate, build_parser


@pytest.fixture
async def client():
    faceplate = Faceplate(serial_port=0, http_port=0)
    async with TestClient(TestServer(faceplate.web.app)) as test_client:
        yield faceplate, test_client


async def test_index_and_state(client):
    _faceplate, http = client
    page = await http.get("/")
    assert page.status == 200 and 'id="faceplate"' in await page.text()
    state = await (await http.get("/state")).json()
    assert state["firmware"] == "1.4.2" and state["serial_connected"] is False
    script = await http.get("/static/faceplate.js")
    assert script.status == 200


async def test_websocket_receives_state_and_sends_inputs(client):
    faceplate, http = client
    ws = await http.ws_connect("/ws")
    first = await ws.receive_json()
    assert len(first["mouth"]) == 8
    await ws.send_json({"type": "button"})
    await ws.send_json({"type": "knob", "direction": "down"})
    await ws.send_json({"type": "bogus"})
    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(faceplate.arduino.outbox) >= 2:
            break
    assert faceplate.arduino.outbox == ["mycroft.stop", "volume.down"]
    faceplate.arduino.handle_line("eyes.color=255")
    await faceplate.web.broadcast_if_changed()
    pushed = await ws.receive_json()
    assert pushed["eyes"][0] == [0, 0, 255]
    await faceplate.web.broadcast_if_changed()
    assert faceplate.web._last_payload
    await ws.close()


def test_cli_defaults():
    args = build_parser().parse_args([])
    assert args.serial_port == 5555 and args.http_port == 8765 and args.host == "127.0.0.1"
