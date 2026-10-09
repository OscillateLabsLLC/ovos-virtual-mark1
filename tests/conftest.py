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
