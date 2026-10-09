"""Port of the firmware's MycroftMouth: the 32x8 matrix and its animations."""

import logging
from enum import Enum

from ovos_virtual_mark1 import mouth_images
from ovos_virtual_mark1.clock import Clock
from ovos_virtual_mark1.fonts import FONT_5X4, FONT_8X4
from ovos_virtual_mark1.framebuffer import WIDTH, Matrix, draw_text, text_width

LOG = logging.getLogger(__name__)

PLATES = 4
PLATE_SIZE = 8
TEXT_Y = 2
TEXT_STEP_MS = 150
LISTEN_FRAMES, LISTEN_STEP_MS = 6, 70
THINK_FRAMES, THINK_STEP_MS = 7, 120
FAKETALK_FRAMES, FAKETALK_STEP_MS = 4, 70
VISEME_MAX = 6
SINGLE_ICON_LIMIT = 60
JOINED_ICON_LIMIT = 90
CONTINUATION = "$"
CODE_BASE = ord("A")


class MouthState(Enum):
    NONE = "none"
    TALK = "talk"
    LISTEN = "listen"
    THINK = "think"
    TEXT = "text"
    VISEME = "viseme"
    ICON = "icon"


ANIMATIONS = {
    MouthState.TALK: mouth_images.TALK_ANIMATION,
    MouthState.LISTEN: mouth_images.LISTEN_ANIMATION,
    MouthState.THINK: mouth_images.THINK_ANIMATION,
    MouthState.VISEME: mouth_images.MOUTH_VISEMES,
}


class Mouth:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.matrix = Matrix()
        self.state = MouthState.NONE
        self.last_state = MouthState.NONE
        self.frame = 0
        self.remaining = 0
        self.next_time = 0
        self.text = ""
        self.text_width = 0
        self.text_idx = 0
        self._icon_hold = ""

    def reset(self) -> None:
        self.state = MouthState.NONE
        self.text_width = 0
        self.text_idx = 0
        self.matrix.clear()

    def update(self) -> None:
        """Called every main-loop pass, exactly like MycroftMouth::update."""
        if self.state is MouthState.TALK:
            self.talk()
        elif self.state is MouthState.LISTEN:
            self.listen()
        elif self.state is MouthState.THINK:
            self.think()
        elif self.state is MouthState.TEXT:
            self._update_text()
        elif self.state is MouthState.NONE and self.last_state is not MouthState.NONE:
            self.reset()
        self.last_state = self.state

    def talk(self) -> None:
        self.state = MouthState.TALK
        self._draw_frame(0, MouthState.TALK)

    def fake_talk(self) -> None:
        """Firmware quirk: update() re-enters talk(), so this shows one frame then rests on frame 0."""
        if self.state is not MouthState.TALK:
            self._reset_counters(MouthState.TALK)
            self.remaining = FAKETALK_FRAMES * 2 - 2
        if self._due():
            self._draw_frame(self.frame, self.state)
            self.frame += 1 if self.frame < FAKETALK_FRAMES - 1 else -1
            self.next_time = self.clock.now_ms() + FAKETALK_STEP_MS
            self.remaining -= 1

    def listen(self) -> None:
        if self.state is not MouthState.LISTEN:
            self._reset_counters(MouthState.LISTEN)
        if self._due():
            self._draw_frame(self.frame, self.state)
            self.frame = self.frame + 1 if self.frame < LISTEN_FRAMES - 1 else 0
            self.next_time = self.clock.now_ms() + LISTEN_STEP_MS

    def think(self) -> None:
        if self.state is not MouthState.THINK:
            self._reset_counters(MouthState.THINK)
            self.remaining = THINK_FRAMES * 2
        if self._due():
            self._draw_frame(self._think_frame(self.frame), self.state)
            self.frame += 1
            self.next_time = self.clock.now_ms() + THINK_STEP_MS
            self.remaining -= 1
        if self.remaining == 0:
            self._reset_counters(MouthState.THINK)
            self.remaining = THINK_FRAMES * 2

    def viseme(self, code: str) -> None:
        if self.state in (MouthState.TEXT, MouthState.ICON):
            return
        self.state = MouthState.VISEME
        index = ord(code[0]) - ord("0") if code else 0
        self._draw_frame(min(max(index, 0), VISEME_MAX), MouthState.VISEME)

    def write(self, text: str) -> None:
        self.text = text
        self.text_width = text_width(text, FONT_5X4)
        self.text_idx = 0
        self._reset_counters(MouthState.TEXT)
        self._update_text()

    def static_text(self, text: str, x: int, large: bool) -> None:
        font = FONT_8X4 if large else FONT_5X4
        draw_text(self.matrix, text, x, 0, font)

    def show_icon(self, code: str) -> None:
        """Port of MycroftMouth::showIcon, including the two-part `$` message protocol."""
        icon = self._join_icon_parts(code)
        if icon is None:
            return
        cursor, x, y, clear_before = _parse_icon_prefix(icon)
        if cursor + 2 > len(icon):
            return
        width = ord(icon[cursor]) - CODE_BASE
        height = ord(icon[cursor + 1]) - CODE_BASE
        cursor += 2
        if len(icon) - cursor < width * 2:
            LOG.warning("mouth.icon payload too short for a %dx%d image", width, height)
            return
        if clear_before == "1":
            self.matrix.clear()
        self._draw_icon_columns(icon[cursor:], width, height, x, y)
        self.state = MouthState.ICON

    def _join_icon_parts(self, code: str) -> str | None:
        if code.endswith(CONTINUATION):
            self._icon_hold = code[:-1]
            return None
        if code.startswith(CONTINUATION):
            if not self._icon_hold:
                return None
            joined, self._icon_hold = self._icon_hold + code[1:], ""
            if len(joined) >= JOINED_ICON_LIMIT:
                LOG.warning("mouth.icon two-part message exceeds %d chars; real firmware drops it", JOINED_ICON_LIMIT)
                return None
            return joined
        if len(code) > SINGLE_ICON_LIMIT:
            LOG.warning("mouth.icon longer than %d chars; real firmware truncates it", SINGLE_ICON_LIMIT)
        return code[:SINGLE_ICON_LIMIT]

    def _draw_icon_columns(self, data: str, width: int, height: int, x: int, y: int) -> None:
        words = [ord(ch) - CODE_BASE for ch in data if ch >= "A"]
        for column in range(width):
            pair = words[column * 2 : column * 2 + 2]
            if len(pair) < 2:
                return
            self.matrix.blit(pair, 1, height, x + column, y)

    def _update_text(self) -> None:
        if not self._due():
            return
        self.matrix.clear()
        draw_text(self.matrix, self.text, WIDTH - self.text_idx, TEXT_Y, FONT_5X4)
        if self.text_width > WIDTH:
            self.text_idx = (self.text_idx + 1) % (self.text_width + WIDTH)
        else:
            self.text_idx = WIDTH - int((WIDTH - self.text_width) / 2)
        self.next_time = self.clock.now_ms() + TEXT_STEP_MS

    def _draw_frame(self, frame: int, animation: MouthState) -> None:
        self.matrix.clear()
        for plate in range(PLATES):
            image = ANIMATIONS[animation][frame * PLATES + plate]
            self.matrix.blit(image, PLATE_SIZE, PLATE_SIZE, plate * PLATE_SIZE, 0)

    def _reset_counters(self, state: MouthState) -> None:
        self.state = state
        self.frame = 0
        self.next_time = 0

    def _due(self) -> bool:
        return self.clock.now_ms() > self.next_time

    @staticmethod
    def _think_frame(step: int) -> int:
        """0,1,...,6,6,5,...,0 over fourteen steps."""
        if step >= THINK_FRAMES:
            return step - ((step - THINK_FRAMES + 1) * 2 - 1)
        return step


def _parse_icon_prefix(icon: str) -> tuple[int, int, int, str]:
    """Consume optional `x=#,`, `y=#,`, `cP=#,` and `cT=#,` fields; return (cursor, x, y, clear_flag)."""
    cursor, x, y, clear_flag = 0, 0, 0, "1"
    if icon.startswith("x=", cursor):
        cursor, x = _parse_number(icon, cursor + 2)
    if icon.startswith("y=", cursor):
        cursor, y = _parse_number(icon, cursor + 2)
    if icon.startswith("cP=", cursor):
        clear_flag = icon[cursor + 3] if cursor + 3 < len(icon) else ""
        cursor += 5
    if icon.startswith("cT=", cursor):
        cursor, _ = _parse_number(icon, cursor + 3)
    return cursor, x, y, clear_flag


def _parse_number(text: str, cursor: int) -> tuple[int, int]:
    value = 0
    while cursor < len(text) and text[cursor] != ",":
        value = value * 10 + ord(text[cursor]) - ord("0")
        cursor += 1
    return cursor + 1, value
