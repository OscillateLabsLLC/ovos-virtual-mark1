"""Port of the firmware's MycroftEyes: two 12-pixel NeoPixel rings and their animations.

Pixels 0-11 are the ring the firmware calls RIGHT, 12-23 the ring it calls LEFT.
Integer widths follow the AVR types (r1/r2 are uint8_t) because the look
animations rely on the wrap-around.
"""

from enum import Enum

from ovos_virtual_mark1.clock import Clock

NUM_PIXELS = 24
RING = NUM_PIXELS // 2
HALF_RING = RING // 2
MAX_BRIGHTNESS = 30
MIN_BRIGHTNESS = 1
DEFAULT_COLOR = (112, 101, 106)
VOLUME_HOLD_MS = 3000
LOOK_STEPS = 6
NARROW_DEPTH = 2
UINT8 = 0xFF
LAST_PIXEL = NUM_PIXELS - 1


class Side(Enum):
    BOTH = "b"
    LEFT = "l"
    RIGHT = "r"
    UP = "u"
    DOWN = "d"
    CROSS = "c"

    @classmethod
    def parse(cls, char: str) -> "Side":
        return {s.value: s for s in cls}.get(char, cls.BOTH)


class Anim(Enum):
    BLINK = "blink"
    NARROW = "narrow"
    LOOK = "look"
    UNLOOK = "unlook"
    WIDEN = "widen"
    VOLUME = "volume"
    SPIN = "spin"
    TIMEDSPIN = "timedspin"
    REFILL = "refill"
    NONE = "none"


class State(Enum):
    OPEN = "open"
    LOOKING = "looking"
    NARROWED = "narrowed"
    ANIMATING = "animating"
    CUSTOM = "custom"


LOOK_START = {Side.UP: (5, 11), Side.DOWN: (11, 5), Side.LEFT: (8, 2), Side.RIGHT: (2, 8), Side.CROSS: (2, 8)}
ANIM_DELAY_MS = {
    Anim.BLINK: 35,
    Anim.LOOK: 70,
    Anim.UNLOOK: 70,
    Anim.NARROW: 140,
    Anim.WIDEN: 140,
    Anim.SPIN: 60,
    Anim.TIMEDSPIN: 60,
    Anim.REFILL: 60,
}


def pack(r: int, g: int, b: int) -> int:
    return (r << 16) | (g << 8) | b


def unpack(color: int) -> tuple[int, int, int]:
    return (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF


class Eyes:
    def __init__(self, clock: Clock, serial_out: list[str]) -> None:
        self.clock = clock
        self.serial_out = serial_out
        self.pixels = [0] * NUM_PIXELS
        self.bright = MAX_BRIGHTNESS
        self.color = pack(*DEFAULT_COLOR)
        self.current_anim = Anim.NONE
        self.current_state = State.OPEN
        self.current_side = self.queued_side = self.look_side = Side.BOTH
        self.queued_anim = Anim.NONE
        self.is_queued = self.back = False
        self.r1 = self.r2 = 0
        self.pos = self.narrow_pos = self.last_pos = self.initial_pos = 0
        self.end_pos = self.start_pos = self.left_jump = 0
        self.delay_ms = 0
        self.next_time = self.end_time = 0
        self.paint = 0

    # ---- public commands -------------------------------------------------

    def setup(self) -> None:
        self.bright = MAX_BRIGHTNESS
        self.color = pack(*DEFAULT_COLOR)
        self.current_anim = Anim.NONE
        self.start_anim(Anim.SPIN, Side.BOTH)

    def update_animation(self) -> None:
        if self.current_anim is Anim.NONE:
            if self.current_state is State.OPEN:
                self.on()
        elif self.current_anim is Anim.VOLUME:
            if self.clock.now_ms() > self.next_time:
                self.current_anim = Anim.NONE
        elif self.current_anim is Anim.TIMEDSPIN:
            if self.clock.now_ms() > self.end_time:
                self.off()
            else:
                self._run_anim()
        else:
            self._run_anim()

    def update_color(self, r: int, g: int, b: int) -> None:
        self.color = pack(r, g, b)
        self.on()

    def update_brightness(self, level: int) -> None:
        self.bright = level
        self.serial_out.extend(["update", str(level)])
        self.on()

    def on(self) -> None:
        self.set(Side.BOTH, self.color)

    def off(self) -> None:
        self.current_anim = Anim.NONE
        self.current_state = State.CUSTOM
        self.set(Side.BOTH, 0)

    def reset(self) -> None:
        if self.current_anim in (Anim.SPIN, Anim.TIMEDSPIN):
            self.start_anim(Anim.REFILL, self.current_side)
        else:
            self.on()
            self.current_state = State.OPEN
            self.current_anim = Anim.NONE

    def set(self, side: Side, color: int) -> None:
        begin = 0 if side in (Side.BOTH, Side.RIGHT) else RING
        end = NUM_PIXELS if side in (Side.BOTH, Side.LEFT) else RING
        for i in range(NUM_PIXELS):
            self.pixels[i] = color if begin <= i < end else 0

    def fill(self, pixel: int) -> None:
        if pixel == LAST_PIXEL:
            self.reset()
            return
        self.current_anim = Anim.NONE
        self.current_state = State.CUSTOM
        for i in range(NUM_PIXELS):
            self.pixels[i] = self.color if i <= pixel else 0

    def set_pixel(self, pixel: int, color: int) -> None:
        if pixel < NUM_PIXELS:
            self.current_anim = Anim.NONE
            self.current_state = State.CUSTOM
            self.pixels[pixel] = color

    def show_volume(self, side: Side, level: int) -> None:
        self.current_side = side
        self.current_anim = Anim.VOLUME
        for j in range(RING):
            lit = self.color if j <= level else 0
            if side in (Side.LEFT, Side.BOTH):
                self.pixels[j] = lit
            if side in (Side.RIGHT, Side.BOTH):
                self.pixels[j + RING] = lit
        self.next_time = self.clock.now_ms() + VOLUME_HOLD_MS

    def timed_spin(self, length_ms: int) -> None:
        self.end_time = self.clock.now_ms() + length_ms
        self.start_anim(Anim.TIMEDSPIN, Side.BOTH)

    def start_anim(self, anim: Anim, side: Side) -> None:
        if self.current_state is State.NARROWED and anim is not Anim.WIDEN:
            self._insert_transition(Anim.WIDEN, anim, side)
            return
        if self.current_state is State.LOOKING and anim is not Anim.UNLOOK:
            self._insert_transition(Anim.UNLOOK, anim, side)
            return
        self._anim_setup(anim, side)
        self._run_anim()

    # ---- animation engine -------------------------------------------------

    def _insert_transition(self, transition: Anim, anim: Anim, side: Side) -> None:
        self.queued_anim, self.queued_side, self.is_queued = anim, side, True
        if transition is Anim.WIDEN:
            self.start_anim(Anim.WIDEN, Side.BOTH)
        else:
            self.start_anim(Anim.UNLOOK, self.look_side)

    def _anim_setup(self, anim: Anim, side: Side) -> None:
        self.current_anim = anim
        if anim is Anim.LOOK:
            self.look_side = side
        self.current_side = side
        if anim not in (Anim.WIDEN, Anim.UNLOOK, Anim.REFILL):
            self.on()
        self.current_state = State.ANIMATING
        self._reset_vars()

    def _end_anim(self, end_state: State) -> None:
        self.current_state = end_state
        self.current_anim = Anim.NONE
        if self.is_queued:
            self.is_queued = False
            self.start_anim(self.queued_anim, self.queued_side)

    def _run_anim(self) -> None:
        if self.clock.now_ms() < self.next_time:
            return
        renderers = {
            Anim.LOOK: lambda: self._render_look(False),
            Anim.UNLOOK: lambda: self._render_look(True),
            Anim.BLINK: lambda: self._render_narrow(self.back),
            Anim.NARROW: lambda: self._render_narrow(False),
            Anim.WIDEN: lambda: self._render_narrow(True),
            Anim.SPIN: self._render_spin,
            Anim.TIMEDSPIN: self._render_spin,
            Anim.REFILL: self._render_refill,
        }
        render = renderers.get(self.current_anim)
        if render:
            render()
        self._update_counters()
        self.next_time = self.clock.now_ms() + self.delay_ms

    def _update_counters(self) -> None:
        updaters = {
            Anim.LOOK: lambda: self._update_look(False),
            Anim.UNLOOK: lambda: self._update_look(True),
            Anim.NARROW: self._update_narrow,
            Anim.WIDEN: self._update_widen,
            Anim.BLINK: self._update_blink,
            Anim.SPIN: self._update_spin,
            Anim.TIMEDSPIN: self._update_spin,
            Anim.REFILL: self._update_refill,
        }
        update = updaters.get(self.current_anim)
        if update:
            update()

    def _update_look(self, unlook: bool) -> None:
        direction = -1 if unlook else 1
        self.pos += direction
        if self.pos == self.end_pos:
            self._end_anim(State.OPEN if unlook else State.LOOKING)
            return
        self.r1 = (self.r1 + direction) & UINT8 if self.r1 + direction <= RING else 0
        self.r2 = (self.r2 - direction) & UINT8 if self.r2 - direction >= 0 else RING

    def _render_look(self, unlook: bool) -> None:
        self.paint = self.color if unlook else 0
        for index in (self.r1, self.r2, (self.r1 + self.left_jump) % RING + RING, (self.r2 + self.left_jump) % RING + RING):
            self._paint_pixel(index)

    def _update_narrow(self) -> None:
        self.narrow_pos += 1
        if self.narrow_pos >= NARROW_DEPTH:
            self._end_anim(State.NARROWED)

    def _update_widen(self) -> None:
        self.narrow_pos -= 1
        if self.narrow_pos < 0:
            self._end_anim(State.OPEN)

    def _update_blink(self) -> None:
        if not self.back:
            self.narrow_pos += 1
            if self.narrow_pos > NARROW_DEPTH:
                self.back = True
        else:
            self.narrow_pos -= 1
            if self.narrow_pos <= 0:
                self._end_anim(State.OPEN)

    def _update_spin(self) -> None:
        self.last_pos = self.pos
        self.pos = (self.pos + 1) % RING

    def _render_spin(self) -> None:
        if self.current_side in (Side.RIGHT, Side.BOTH):
            self._paint_pixel(self.pos, self.color)
            self._paint_pixel(self.last_pos, 0)
        if self.current_side in (Side.LEFT, Side.BOTH):
            self._paint_pixel(self.pos + self.left_jump, self.color)
            self._paint_pixel(self.last_pos + self.left_jump, 0)

    def _update_refill(self) -> None:
        self.pos += 1
        if self.pos == self.initial_pos:
            self._end_anim(State.OPEN)
        if self.pos >= RING:
            self.pos = 0

    def _render_refill(self) -> None:
        if self.current_side in (Side.RIGHT, Side.BOTH):
            self._paint_pixel(self.pos, self.color)
        if self.current_side in (Side.LEFT, Side.BOTH):
            self._paint_pixel(self.pos + self.left_jump, self.color)

    def _render_narrow(self, widen: bool) -> None:
        self.paint = self.color if widen else 0
        if self.current_side in (Side.RIGHT, Side.BOTH):
            self._set_eye_narrow(self.narrow_pos, 0)
        if self.current_side in (Side.LEFT, Side.BOTH):
            self._set_eye_narrow(self.narrow_pos, RING)

    def _set_eye_narrow(self, position: int, offset: int) -> None:
        for index in (
            position + offset,
            RING - position - 1 + offset,
            HALF_RING + position + offset,
            HALF_RING - position - 1 + offset,
        ):
            self._paint_pixel(index)

    def _paint_pixel(self, index: int, color: int | None = None) -> None:
        if 0 <= index < NUM_PIXELS:
            self.pixels[index] = self.paint if color is None else color

    def _set_look_vars(self, side: Side, unlook: bool) -> None:
        self.pos = LOOK_STEPS if unlook else 0
        look_start, unlook_start = LOOK_START.get(side, (0, 0))
        self.start_pos = unlook_start if unlook else look_start
        self.end_pos = 0 if unlook else LOOK_STEPS
        self.r1 = self.start_pos
        self.r2 = 0 if self.start_pos + 1 > RING - 1 else self.start_pos + 1

    def _reset_vars(self) -> None:
        self.left_jump = 0
        self.next_time = 0
        anim = self.current_anim
        self.delay_ms = ANIM_DELAY_MS.get(anim, 0)
        if anim is Anim.BLINK:
            self.narrow_pos, self.back = 0, False
        elif anim in (Anim.LOOK, Anim.UNLOOK):
            self._set_look_vars(self.current_side, anim is Anim.UNLOOK)
            if self.current_side is Side.CROSS:
                self.left_jump = HALF_RING
        elif anim is Anim.NARROW:
            self.narrow_pos = 0
        elif anim is Anim.WIDEN:
            self.narrow_pos = NARROW_DEPTH
        elif anim in (Anim.SPIN, Anim.TIMEDSPIN):
            self.pos = 0
        elif anim is Anim.REFILL:
            self.initial_pos = self.pos
        self.left_jump += RING
