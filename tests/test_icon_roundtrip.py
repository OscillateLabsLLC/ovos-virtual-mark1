"""Decode what ovos-mark1-utils encodes, split exactly as ovos-PHAL-plugin-mk1 splits it."""

import warnings

import pytest

from ovos_virtual_mark1.arduino import VirtualArduino

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from ovos_mark1.faceplate import FaceplateGrid

PLUGIN_SPLIT_AT = 31
PLUGIN_LIMIT = 60


class FakeBus:
    def on(self, *_args, **_kwargs):
        pass

    def emit(self, *_args, **_kwargs):
        pass


def plugin_messages(img_code: str, x: int = 0, y: int = 0, refresh: bool = False) -> list[str]:
    """Mirror ovos_PHAL_plugin_mk1._do_display's message construction and splitting."""
    message = f"mouth.icon=x={x},y={y},cP={int(refresh)},{img_code}"
    if len(message) > PLUGIN_LIMIT:
        return [message[:PLUGIN_SPLIT_AT] + "$", "mouth.icon=$" + message[PLUGIN_SPLIT_AT:]]
    return [message]


def grid_pixels(rows: list[list[int]]) -> set[tuple[int, int]]:
    return {(x, y) for y, row in enumerate(rows) for x, v in enumerate(row) if v}


@pytest.fixture
def pattern() -> list[list[int]]:
    return [[1 if (x + y) % 3 == 0 or x == y else 0 for x in range(32)] for y in range(8)]


def test_full_width_image_roundtrip(arduino: VirtualArduino, pattern):
    code = FaceplateGrid(grid=pattern, bus=FakeBus()).encode(invert=False)
    assert code.startswith("aI")
    for line in plugin_messages(code, refresh=True):
        arduino.handle_line(line)
    assert arduino.mouth.matrix.lit() == grid_pixels(pattern)


def test_half_width_image_with_offset(arduino: VirtualArduino, pattern):
    half = [row[:16] for row in pattern]
    code = FaceplateGrid(grid=half, bus=FakeBus()).encode(invert=False)
    for line in plugin_messages(code, x=16, refresh=True):
        arduino.handle_line(line)
    assert arduino.mouth.matrix.lit() == {(x + 16, y) for x, y in grid_pixels(half)}


def test_inverted_encoding_flips_pixels(arduino: VirtualArduino, pattern):
    code = FaceplateGrid(grid=pattern, bus=FakeBus()).encode(invert=True)
    for line in plugin_messages(code, refresh=True):
        arduino.handle_line(line)
    everything = {(x, y) for x in range(32) for y in range(8)}
    assert arduino.mouth.matrix.lit() == everything - grid_pixels(pattern)
