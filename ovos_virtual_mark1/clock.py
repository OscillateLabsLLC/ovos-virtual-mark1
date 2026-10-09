"""Millisecond clocks: a monotonic one for runtime and a manual one for tests."""

import time


class Clock:
    def now_ms(self) -> int:
        return int(time.monotonic() * 1000)


class ManualClock(Clock):
    def __init__(self, start_ms: int = 0) -> None:
        self._now = start_ms

    def now_ms(self) -> int:
        return self._now

    def advance(self, ms: int) -> None:
        self._now += ms
