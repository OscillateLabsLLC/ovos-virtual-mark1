"""TCP stand-in for the Arduino's serial port, reachable via pyserial's `socket://` URLs."""

import asyncio
import logging

from ovos_virtual_mark1.arduino import VirtualArduino

LOG = logging.getLogger(__name__)
LINE_END = "\r\n"
# A real Pro Mini resets on DTR when the port opens and its bootloader pauses before
# the sketch prints the banner. pyserial's socket transport also discards anything
# that arrives during open(), so an instant banner would be lost on a fast host.
BOOT_DELAY_S = 0.25


class SerialServer:
    def __init__(
        self, arduino: VirtualArduino, host: str = "127.0.0.1", port: int = 5555, boot_delay_s: float = BOOT_DELAY_S
    ) -> None:
        self.arduino = arduino
        self.host = host
        self.port = port
        self.boot_delay_s = boot_delay_s
        self._server: asyncio.AbstractServer | None = None
        self._writers: set[asyncio.StreamWriter] = set()

    @property
    def client_count(self) -> int:
        return len(self._writers)

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._serve, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        LOG.info("virtual serial port listening on socket://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        for writer in list(self._writers):
            writer.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def flush(self) -> None:
        """Deliver everything the Arduino has queued; with no client attached the lines are lost, as on real serial."""
        lines, self.arduino.outbox[:] = list(self.arduino.outbox), []
        if not lines or not self._writers:
            return
        payload = "".join(line + LINE_END for line in lines).encode()
        for writer in list(self._writers):
            try:
                writer.write(payload)
                await writer.drain()
            except (ConnectionError, RuntimeError):
                self._writers.discard(writer)

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        LOG.info("serial client connected: %s", peer)
        self._writers.add(writer)
        try:
            await asyncio.sleep(self.boot_delay_s)
            self.arduino.on_connect()
            await self.flush()
            while raw := await reader.readline():
                self.arduino.handle_line(raw.decode("utf-8", errors="replace").rstrip(LINE_END))
                await self.flush()
        except ConnectionError:
            pass
        finally:
            self._writers.discard(writer)
            writer.close()
            LOG.info("serial client disconnected: %s", peer)
