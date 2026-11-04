"""The virtual Arduino: parses the Mark 1 serial protocol and owns the faceplate state."""

import logging
from dataclasses import dataclass, field

from ovos_virtual_mark1.clock import Clock
from ovos_virtual_mark1.eyes import Anim, Eyes, Side, unpack
from ovos_virtual_mark1.mouth import Mouth, MouthState

LOG = logging.getLogger(__name__)

FIRMWARE_VERSION = "1.4.2"
BANNER = f"Mycroft Mark 1 v{FIRMWARE_VERSION} - Connected"
VERSION_REPLY = f"Mycroft Mark 1 v{FIRMWARE_VERSION}"
COMMAND_ECHO = "Command: "
BUTTON_PRESS = "mycroft.stop"
VOLUME_UP, VOLUME_DOWN = "volume.up", "volume.down"
LED_BLINK_MS = 500
TEMPERATURE_X = {1: 18, 2: 16}
NEGATIVE_THREE_DIGIT_X, THREE_DIGIT_X = 13, 14
DEGREE_GLYPH = "\\"


@dataclass
class SystemFlags:
    muted: bool = False
    led_blink_count: int = 0
    led_blink_started_ms: int = 0
    led_blink_period_ms: int = LED_BLINK_MS * 2


@dataclass
class VirtualArduino:
    clock: Clock = field(default_factory=Clock)
    outbox: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.mouth = Mouth(self.clock)
        self.eyes = Eyes(self.clock, self.outbox)
        self.system = SystemFlags()
        self.last_command = ""
        self.eyes.setup()

    # ---- serial side ------------------------------------------------------

    def on_connect(self) -> None:
        self.outbox.append(BANNER)

    def handle_line(self, line: str) -> None:
        """Process one `class.command=param` line the way enclosure.ino's loop() does."""
        self.last_command = line
        self.outbox.append(COMMAND_ECHO + line)
        if line == "version":
            self.outbox.append(VERSION_REPLY)
            return
        namespace, _, command = line.partition(".")
        handler = {
            "mouth": self._mouth_command,
            "eyes": self._eyes_command,
            "system": self._system_command,
            "weather": self._weather_command,
        }.get(namespace)
        if handler is None:
            LOG.debug("ignoring unknown command %r", line)
            return
        handler(command)

    def tick(self) -> None:
        """One idle pass of the firmware loop: animate, then stop the boot spin once the mouth is busy."""
        self.eyes.update_animation()
        self.mouth.update()
        if self.mouth.state is not MouthState.NONE and self.eyes.current_anim is Anim.SPIN:
            self.eyes.reset()

    # ---- physical inputs --------------------------------------------------

    def press_button(self) -> None:
        self.outbox.append(BUTTON_PRESS)

    def turn_knob(self, clockwise: bool) -> None:
        self.outbox.append(VOLUME_UP if clockwise else VOLUME_DOWN)

    # ---- snapshot for the GUI ---------------------------------------------

    def snapshot(self) -> dict:
        return {
            "mouth": self.mouth.matrix.rows(),
            "mouth_state": self.mouth.state.value,
            "eyes": [list(unpack(c)) for c in self.eyes.pixels],
            "eyes_anim": self.eyes.current_anim.value,
            "brightness": self.eyes.bright,
            "muted": self.system.muted,
            "led": self._led_state(),
            "firmware": FIRMWARE_VERSION,
            "last_command": self.last_command,
        }

    def _led_state(self) -> bool:
        elapsed = self.clock.now_ms() - self.system.led_blink_started_ms
        if elapsed >= self.system.led_blink_count * self.system.led_blink_period_ms:
            return False
        return (elapsed % self.system.led_blink_period_ms) < LED_BLINK_MS

    # ---- command namespaces -----------------------------------------------

    def _mouth_command(self, cmd: str) -> None:
        if cmd.startswith("reset"):
            self.mouth.reset()
        elif cmd.startswith("faketalk"):
            self.mouth.fake_talk()
        elif cmd.startswith("talk"):
            self.mouth.talk()
        elif cmd.startswith("listen"):
            self.mouth.listen()
        elif cmd.startswith("think"):
            self.mouth.think()
        elif cmd.startswith("text="):
            self.mouth.write(cmd[5:])
        elif cmd.startswith("icon"):
            self.mouth.show_icon(cmd[5:])
        elif cmd.startswith("viseme="):
            self.mouth.viseme(cmd[7:])

    def _eyes_command(self, cmd: str) -> None:
        if cmd.startswith("color="):
            self.eyes.update_color(*unpack(_to_int(cmd[6:])))
        elif cmd.startswith("level="):
            self.eyes.update_brightness(_to_int(cmd[6:]) & 0xFF)
        elif cmd.startswith("fill="):
            self.eyes.fill(_to_int(cmd[5:]) & 0xFF)
        elif cmd.startswith("volume="):
            self.eyes.show_volume(Side.BOTH, _to_int(cmd[7:]) & 0xFF)
        elif cmd.startswith("spin="):
            self.eyes.timed_spin(_to_int(cmd[5:]))
        elif cmd.startswith("on"):
            self.eyes.on()
        elif cmd.startswith("off"):
            self.eyes.off()
        elif cmd.startswith("set"):
            pixel, _, color = cmd[4:].partition(",")
            self.eyes.set_pixel(_to_int(pixel), _to_int(color))
        elif cmd.startswith("reset"):
            self.eyes.reset()
        else:
            self._eyes_animation(cmd)

    def _eyes_animation(self, cmd: str) -> None:
        for term, anim in (
            ("blink", Anim.BLINK),
            ("narrow", Anim.NARROW),
            ("look", Anim.LOOK),
            ("widen", Anim.WIDEN),
            ("unlook", Anim.UNLOOK),
            ("spin", Anim.SPIN),
        ):
            if cmd.startswith(term):
                side_arg = cmd.replace(term + "=", "", 1)
                self.eyes.start_anim(anim, Side.parse(side_arg[:1]))
                return

    def _system_command(self, cmd: str) -> None:
        if cmd.startswith("reset"):
            self._reboot()
        elif cmd.startswith("mute"):
            self.system.muted = True
        elif cmd.startswith("unmute"):
            self.system.muted = False
        elif cmd.startswith("blink="):
            self.system.led_blink_count = _to_int(cmd[6:])
            self.system.led_blink_started_ms = self.clock.now_ms()
        elif cmd.startswith("version"):
            self.outbox.append(VERSION_REPLY)

    def _weather_command(self, cmd: str) -> None:
        if not cmd.startswith("display="):
            return
        temperature, _, icon = cmd[8:].partition(",")
        self.mouth.reset()
        self.mouth.show_icon(icon)
        self.mouth.static_text(temperature + DEGREE_GLYPH, _temperature_x(temperature), large=True)

    def _reboot(self) -> None:
        self.system = SystemFlags()
        self.mouth = Mouth(self.clock)
        self.eyes = Eyes(self.clock, self.outbox)
        self.eyes.setup()
        self.outbox.append(BANNER)


def _temperature_x(temperature: str) -> int:
    if len(temperature) == 3:
        return NEGATIVE_THREE_DIGIT_X if temperature[0] == "-" else THREE_DIGIT_X
    return TEMPERATURE_X.get(len(temperature), 0)


def _to_int(text: str) -> int:
    """Arduino String::toInt(): leading integer, or 0 when there is none."""
    digits = ""
    for ch in text.strip():
        if ch.isdigit() or (ch == "-" and not digits):
            digits += ch
        else:
            break
    try:
        return int(digits)
    except ValueError:
        return 0
