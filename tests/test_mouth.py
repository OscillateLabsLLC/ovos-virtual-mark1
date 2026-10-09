import pytest

from ovos_virtual_mark1 import mouth_images
from ovos_virtual_mark1.clock import ManualClock
from ovos_virtual_mark1.mouth import LISTEN_STEP_MS, TEXT_STEP_MS, THINK_STEP_MS, Mouth, MouthState


@pytest.fixture
def mouth(clock: ManualClock) -> Mouth:
    return Mouth(clock)


def frame_pixels(animation: list[list[int]], frame: int) -> set[tuple[int, int]]:
    probe = Mouth(ManualClock())
    for plate in range(4):
        probe.matrix.blit(animation[frame * 4 + plate], 8, 8, plate * 8, 0)
    return probe.matrix.lit()


def test_talk_shows_frame_zero_and_stays(mouth, clock):
    mouth.talk()
    expected = frame_pixels(mouth_images.TALK_ANIMATION, 0)
    assert mouth.matrix.lit() == expected
    clock.advance(500)
    mouth.update()
    assert mouth.matrix.lit() == expected and mouth.state is MouthState.TALK


def test_listen_cycles_six_frames(mouth, clock):
    mouth.listen()
    seen = [mouth.matrix.lit()]
    for _ in range(6):
        clock.advance(LISTEN_STEP_MS + 1)
        mouth.update()
        seen.append(mouth.matrix.lit())
    assert seen[0] == frame_pixels(mouth_images.LISTEN_ANIMATION, 0)
    assert seen[1] == frame_pixels(mouth_images.LISTEN_ANIMATION, 1)
    assert seen[6] == seen[0]
    assert len({frozenset(s) for s in seen[:6]}) == 6


def test_think_plays_forward_then_backward(mouth, clock):
    mouth.think()
    frames = [mouth.matrix.lit()]
    for _ in range(13):
        clock.advance(THINK_STEP_MS + 1)
        mouth.update()
        frames.append(mouth.matrix.lit())
    for k in range(7):
        assert frames[k] == frame_pixels(mouth_images.THINK_ANIMATION, k)
        assert frames[13 - k] == frames[k]


def test_viseme_is_clamped_and_blocked_by_text(mouth):
    mouth.viseme("9")
    assert mouth.matrix.lit() == frame_pixels(mouth_images.MOUTH_VISEMES, 6)
    mouth.viseme("")
    assert mouth.matrix.lit() == frame_pixels(mouth_images.MOUTH_VISEMES, 0)
    mouth.write("HI")
    mouth.viseme("2")
    assert mouth.state is MouthState.TEXT


def test_short_text_is_centered_after_first_tick(mouth, clock):
    mouth.write("HI")
    assert mouth.matrix.lit() == set()
    clock.advance(TEXT_STEP_MS + 1)
    mouth.update()
    assert min(x for x, _ in mouth.matrix.lit()) == 12
    assert all(y >= 2 for _, y in mouth.matrix.lit())


def test_long_text_scrolls_left_one_column_per_tick(mouth, clock):
    mouth.write("HELLO WORLD")
    assert mouth.text_width > 32
    positions = []
    for _ in range(3):
        clock.advance(TEXT_STEP_MS + 1)
        mouth.update()
        positions.append(min(x for x, _ in mouth.matrix.lit()))
    assert positions == [31, 30, 29]


def test_reset_clears_everything(mouth):
    mouth.write("HI")
    mouth.reset()
    assert mouth.state is MouthState.NONE and mouth.matrix.lit() == set()


def test_show_icon_single_message_with_prefix(mouth):
    mouth.matrix.blit([0b1111, 0b1111], 1, 8, 31, 0)
    mouth.show_icon("x=2,y=1,cP=0,BIBB")
    assert mouth.matrix.lit() == {(31, y) for y in range(8)} | {(2, 1), (2, 5)}
    assert mouth.state is MouthState.ICON


def test_show_icon_clears_by_default(mouth):
    mouth.matrix.blit([0b1111, 0b1111], 1, 8, 31, 0)
    mouth.show_icon("BIBA")
    assert mouth.matrix.lit() == {(0, 0)}


def test_show_icon_two_part_message(mouth):
    mouth.show_icon("x=0,y=0,cP=1,CIBA$")
    assert mouth.matrix.lit() == set()
    mouth.show_icon("$AB")
    assert mouth.matrix.lit() == {(0, 0), (1, 4)}


def test_show_icon_rejects_short_payload_and_orphan_continuation(mouth):
    mouth.show_icon("$AB")
    mouth.show_icon("aIAB")
    mouth.show_icon("B")
    assert mouth.matrix.lit() == set() and mouth.state is MouthState.NONE
