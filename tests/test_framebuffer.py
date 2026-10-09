from ovos_virtual_mark1.fonts import FONT_5X4, FONT_8X4
from ovos_virtual_mark1.framebuffer import Matrix, draw_text, text_width


def test_blit_low_bit_is_top_pixel():
    m = Matrix()
    m.blit([0b1000, 0b0001], 1, 8, 5, 0)
    assert m.lit() == {(5, 3), (5, 4)}


def test_blit_overwrites_covered_pixels_only():
    m = Matrix()
    m.blit([0b1111, 0b1111] * 32, 32, 8, 0, 0)
    m.blit([0, 0, 0, 0], 2, 8, 10, 0)
    assert len(m.lit()) == 32 * 8 - 16
    assert (10, 0) not in m.lit() and (11, 7) not in m.lit()


def test_blit_clips_at_edges():
    m = Matrix()
    m.blit([0b0001, 0, 0b0001, 0], 2, 8, 31, 0)
    m.blit([0b0001], 1, 1, -1, 0)
    m.blit([0b0001], 1, 1, 0, 8)
    assert m.lit() == {(31, 0)}


def test_blit_unaligned_y_with_five_row_font_height():
    m = Matrix()
    m.blit([0b1111, 0b0001], 1, 5, 3, 2)
    assert m.lit() == {(3, y) for y in range(2, 7)}


def test_text_width_matches_firmware_quirks():
    assert text_width("", FONT_5X4) == -1
    assert text_width("A", FONT_5X4) == 4
    assert text_width("AB", FONT_5X4) == 4 + 1 + 3
    assert text_width("a", FONT_5X4) == text_width("A", FONT_5X4)
    assert text_width("\x01", FONT_5X4) == -1


def test_draw_text_renders_an_i():
    m = Matrix()
    draw_text(m, "I", 0, 2, FONT_5X4)
    assert m.lit() == {(0, 2), (0, 6), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (2, 2), (2, 6)}


def test_draw_text_stops_at_right_edge_and_skips_offscreen_left():
    m = Matrix()
    draw_text(m, "II", 30, 2, FONT_5X4)
    assert all(x >= 30 for x, _ in m.lit())
    m.clear()
    draw_text(m, "II", -8, 2, FONT_5X4)
    assert m.lit() == set()


def test_large_font_degree_glyph_is_two_by_two():
    m = Matrix()
    draw_text(m, "\\", 0, 0, FONT_8X4)
    assert m.lit() == {(0, 0), (0, 1), (1, 0), (1, 1)}


def test_fonts_have_sixty_four_glyphs():
    for font in (FONT_5X4, FONT_8X4):
        assert len(font.glyphs) == 64 and len(font.widths) == 64
        assert all(len(g) == font.glyph_step for g in font.glyphs)
