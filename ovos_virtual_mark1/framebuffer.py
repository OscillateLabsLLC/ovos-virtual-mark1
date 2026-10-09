"""32x8 monochrome framebuffer that mirrors the HT1632 driver's pixel semantics."""

from dataclasses import dataclass, field
from math import ceil

WIDTH = 32
HEIGHT = 8
NIBBLE_ROWS = 4
FIRST_PRINTABLE = 32
GLYPH_COUNT = 64
LOWER_A, LOWER_Z, CASE_OFFSET = 65, 90, 32


class Matrix:
    """Pixel grid indexed as pixels[y][x]; a blit overwrites every pixel it covers."""

    def __init__(self) -> None:
        self.pixels = [[0] * WIDTH for _ in range(HEIGHT)]

    def clear(self) -> None:
        for row in self.pixels:
            row[:] = [0] * WIDTH

    def get(self, x: int, y: int) -> int:
        return self.pixels[y][x]

    def blit(self, nibbles: list[int], width: int, height: int, x: int, y: int, offset: int = 0) -> None:
        """Draw column-major 4-bit words; bit 0 of each word is the topmost pixel of its group."""
        words_per_column = ceil(height / NIBBLE_ROWS)
        for column in range(width):
            px = x + column
            if not 0 <= px < WIDTH:
                continue
            for row in range(height):
                py = y + row
                if not 0 <= py < HEIGHT:
                    continue
                word = nibbles[offset + words_per_column * column + row // NIBBLE_ROWS]
                self.pixels[py][px] = (word >> (row % NIBBLE_ROWS)) & 1

    def rows(self) -> list[str]:
        return ["".join(str(bit) for bit in row) for row in self.pixels]

    def lit(self) -> set[tuple[int, int]]:
        return {(x, y) for y, row in enumerate(self.pixels) for x, bit in enumerate(row) if bit}


@dataclass
class Font:
    """Proportional font in the HT1632 layout: 64 glyphs from ASCII 32, each `glyph_step` nibbles."""

    height: int
    glyph_step: int
    glyphs: list[list[int]]
    widths: list[int]
    nibbles: list[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.nibbles = [word for glyph in self.glyphs for word in glyph]


def glyph_index(char: str) -> int | None:
    """Map a character to its glyph slot, upper-casing letters and dropping anything unprintable."""
    index = ord(char) - FIRST_PRINTABLE
    if LOWER_A <= index <= LOWER_Z:
        index -= CASE_OFFSET
    if 0 <= index < GLYPH_COUNT:
        return index
    return None


def text_width(text: str, font: Font, gutter: int = 1) -> int:
    width = 0
    for char in text:
        index = glyph_index(char)
        if index is not None:
            width += font.widths[index] + gutter
    return width - gutter


def draw_text(matrix: Matrix, text: str, x: int, y: int, font: Font, gutter: int = 1) -> None:
    """Port of HT1632 drawTextPgm, including the gutter column it clears after each glyph."""
    if y + font.height < 0 or y >= HEIGHT:
        return
    cursor = x
    for char in text:
        index = glyph_index(char)
        if index is None:
            continue
        if cursor >= WIDTH:
            return
        width = font.widths[index]
        if cursor + width + gutter >= 0:
            matrix.blit(font.nibbles, width, font.height, cursor, y, index * font.glyph_step)
            for gap in range(gutter):
                matrix.blit(font.nibbles, 1, font.height, cursor + width + gap, y, 0)
        cursor += width + gutter
