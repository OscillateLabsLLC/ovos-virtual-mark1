import asyncio

import pytest

from ovos_virtual_mark1.arduino import VirtualArduino
from ovos_virtual_mark1.clock import ManualClock

START_MS = 1000


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(START_MS)


@pytest.fixture
def arduino(clock: ManualClock) -> VirtualArduino:
    return VirtualArduino(clock=clock)


async def wait_for(predicate, timeout: float = 3.0) -> None:
    """Poll until predicate() is true; CI runners schedule the server coroutines late."""
    for _ in range(int(timeout / 0.02)):
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met in time")
