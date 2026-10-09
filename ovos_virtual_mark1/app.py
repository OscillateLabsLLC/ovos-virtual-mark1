"""Wire the virtual Arduino to its serial and web front-ends and run the main loop."""

import argparse
import asyncio
import logging

from ovos_virtual_mark1.arduino import VirtualArduino
from ovos_virtual_mark1.bus import DEFAULT_BUS_URL, BusLink
from ovos_virtual_mark1.serial_server import SerialServer
from ovos_virtual_mark1.web import WebServer

LOG = logging.getLogger(__name__)
TICK_HZ = 50
DEFAULT_SERIAL_PORT = 5555
DEFAULT_HTTP_PORT = 8765
DEFAULT_HOST = "127.0.0.1"


class Faceplate:
    """One virtual Mark 1: Arduino model plus both servers."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        serial_port: int = DEFAULT_SERIAL_PORT,
        http_port: int = DEFAULT_HTTP_PORT,
        bus_url: str | None = DEFAULT_BUS_URL,
    ) -> None:
        self.arduino = VirtualArduino()
        self.serial = SerialServer(self.arduino, host, serial_port)
        self.bus = BusLink(bus_url) if bus_url else None
        self.web = WebServer(self.state, self.arduino, host, http_port, bus=self.bus)

    def state(self) -> dict:
        return {
            **self.arduino.snapshot(),
            "serial_connected": self.serial.client_count > 0,
            "bus_connected": self.bus is not None and self.bus.connected,
        }

    async def start(self) -> None:
        await self.serial.start()
        await self.web.start()
        if self.bus:
            await self.bus.start()

    async def stop(self) -> None:
        if self.bus:
            await self.bus.stop()
        await self.web.stop()
        await self.serial.stop()

    async def step(self) -> None:
        self.arduino.tick()
        await self.serial.flush()
        await self.web.broadcast_if_changed()

    async def run_forever(self) -> None:
        await self.start()
        try:
            while True:
                await self.step()
                await asyncio.sleep(1 / TICK_HZ)
        finally:
            await self.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ovos-virtual-mark1", description="Virtual Mycroft Mark 1 faceplate for OVOS")
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind address for both servers")
    parser.add_argument(
        "--serial-port", type=int, default=DEFAULT_SERIAL_PORT, help="TCP port the PHAL plugin connects to as socket://HOST:PORT"
    )
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT, help="port for the browser GUI")
    parser.add_argument("--bus", default=DEFAULT_BUS_URL, help="OVOS messagebus websocket URL for the control panel")
    parser.add_argument("--no-bus", action="store_true", help="disable the messagebus link (control panel is read-only)")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        bus_url = None if args.no_bus else args.bus
        asyncio.run(Faceplate(args.host, args.serial_port, args.http_port, bus_url).run_forever())
    except KeyboardInterrupt:
        pass
