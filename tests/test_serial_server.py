"""Exercise the exact seam the PHAL plugin uses: pyserial over a socket:// URL."""

import asyncio

import pytest
import serial

from ovos_virtual_mark1.app import Faceplate
from ovos_virtual_mark1.arduino import BANNER, VERSION_REPLY, VirtualArduino
from ovos_virtual_mark1.serial_server import SerialServer
from tests.conftest import wait_for


async def open_pyserial(port: int) -> serial.Serial:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: serial.serial_for_url(f"socket://127.0.0.1:{port}", timeout=2))


async def readline(ser: serial.Serial) -> bytes:
    return await asyncio.get_running_loop().run_in_executor(None, ser.readline)


@pytest.fixture
async def server():
    arduino = VirtualArduino()
    srv = SerialServer(arduino, "127.0.0.1", 0)
    await srv.start()
    yield srv
    await srv.stop()


async def test_banner_echo_and_version_over_pyserial(server):
    ser = await open_pyserial(server.port)
    try:
        assert await readline(ser) == (BANNER + "\r\n").encode()
        ser.write(b"version\n")
        assert await readline(ser) == b"Command: version\r\n"
        assert await readline(ser) == (VERSION_REPLY + "\r\n").encode()
        ser.write(b"mouth.text=HELLO\n")
        assert await readline(ser) == b"Command: mouth.text=HELLO\r\n"
        await wait_for(lambda: server.arduino.mouth.text == "HELLO")
    finally:
        ser.close()


async def test_button_press_reaches_the_client(server):
    ser = await open_pyserial(server.port)
    try:
        await readline(ser)
        server.arduino.press_button()
        await server.flush()
        assert await readline(ser) == b"mycroft.stop\r\n"
    finally:
        ser.close()


async def test_client_count_tracks_connections(server):
    assert server.client_count == 0
    ser = await open_pyserial(server.port)
    await readline(ser)
    assert server.client_count == 1
    ser.close()
    await wait_for(lambda: server.client_count == 0)


async def test_output_without_client_is_dropped(server):
    server.arduino.press_button()
    await server.flush()
    assert server.arduino.outbox == []


async def test_faceplate_step_runs_both_servers():
    faceplate = Faceplate(serial_port=0, http_port=0)
    await faceplate.start()
    try:
        ser = await open_pyserial(faceplate.serial.port)
        await readline(ser)
        assert faceplate.state()["serial_connected"] is True
        ser.write(b"eyes.color=255\n")
        # The boot spin is still running and darkens individual pixels, so check the
        # colour register the command sets rather than any one pixel.
        await wait_for(lambda: faceplate.arduino.eyes.color == 255)
        await faceplate.step()
        assert faceplate.state()["last_command"] == "eyes.color=255"
        assert faceplate.state()["eyes"].count([0, 0, 255]) >= 20
        ser.close()
    finally:
        await faceplate.stop()
