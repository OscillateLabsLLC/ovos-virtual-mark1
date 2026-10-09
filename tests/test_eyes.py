import pytest

from ovos_virtual_mark1.clock import ManualClock
from ovos_virtual_mark1.eyes import NUM_PIXELS, Anim, Eyes, Side, State, pack

RED = pack(255, 0, 0)


@pytest.fixture
def eyes(clock: ManualClock) -> Eyes:
    e = Eyes(clock, [])
    e.on()
    return e


def lit(eyes: Eyes) -> set[int]:
    return {i for i, c in enumerate(eyes.pixels) if c}


def run(eyes: Eyes, clock: ManualClock, steps: int, step_ms: int) -> None:
    for _ in range(steps):
        clock.advance(step_ms)
        eyes.update_animation()


def test_boot_spin_empties_the_ring_then_chases_one_pixel(clock):
    eyes = Eyes(clock, [])
    eyes.setup()
    assert eyes.current_anim is Anim.SPIN
    assert set(range(NUM_PIXELS)) - lit(eyes) == {0, 12}
    run(eyes, clock, 2, 60)
    assert set(range(NUM_PIXELS)) - lit(eyes) == {0, 1, 12, 13}
    run(eyes, clock, 9, 60)
    assert lit(eyes) == {11, 23}
    run(eyes, clock, 1, 60)
    assert lit(eyes) == {0, 12}


def test_reset_during_spin_refills_then_opens(clock):
    eyes = Eyes(clock, [])
    eyes.setup()
    run(eyes, clock, 3, 60)
    eyes.reset()
    assert eyes.current_anim is Anim.REFILL
    run(eyes, clock, 13, 60)
    assert eyes.current_anim is Anim.NONE and eyes.current_state is State.OPEN
    assert lit(eyes) == set(range(NUM_PIXELS))


def test_color_and_brightness(eyes):
    eyes.update_color(255, 0, 0)
    assert set(eyes.pixels) == {RED}
    eyes.update_brightness(10)
    assert eyes.serial_out == ["update", "10"] and eyes.bright == 10


def test_narrow_closes_from_top_and_bottom(eyes, clock):
    eyes.start_anim(Anim.NARROW, Side.BOTH)
    assert set(range(NUM_PIXELS)) - lit(eyes) == {0, 11, 6, 5, 12, 23, 18, 17}
    run(eyes, clock, 1, 140)
    assert lit(eyes) == {2, 3, 8, 9, 14, 15, 20, 21}
    assert eyes.current_state is State.NARROWED


def test_blink_ends_open_with_everything_lit(eyes, clock):
    eyes.start_anim(Anim.BLINK, Side.LEFT)
    run(eyes, clock, 2, 35)
    assert lit(eyes) == set(range(12))
    run(eyes, clock, 8, 35)
    assert eyes.current_anim is Anim.NONE and eyes.current_state is State.OPEN
    assert lit(eyes) == set(range(NUM_PIXELS))


def test_look_left_leaves_three_pixels_on_the_left_of_each_ring(eyes, clock):
    eyes.start_anim(Anim.LOOK, Side.LEFT)
    run(eyes, clock, 5, 70)
    assert eyes.current_state is State.LOOKING
    assert lit(eyes) == {1, 2, 3, 13, 14, 15}


def test_animation_while_looking_unlooks_first(eyes, clock):
    eyes.start_anim(Anim.LOOK, Side.UP)
    run(eyes, clock, 5, 70)
    eyes.start_anim(Anim.BLINK, Side.BOTH)
    assert eyes.current_anim is Anim.UNLOOK and eyes.is_queued
    run(eyes, clock, 6, 70)
    assert eyes.current_anim is Anim.BLINK


def test_animation_while_narrowed_widens_first(eyes, clock):
    eyes.start_anim(Anim.NARROW, Side.BOTH)
    run(eyes, clock, 1, 140)
    eyes.start_anim(Anim.LOOK, Side.DOWN)
    assert eyes.current_anim is Anim.WIDEN
    run(eyes, clock, 3, 140)
    assert eyes.current_anim is Anim.LOOK


def test_fill_and_set_pixel_are_custom_states(eyes):
    eyes.fill(5)
    assert lit(eyes) == set(range(6)) and eyes.current_state is State.CUSTOM
    eyes.set_pixel(20, RED)
    assert eyes.pixels[20] == RED
    eyes.set_pixel(99, RED)
    eyes.fill(23)
    assert lit(eyes) == set(range(NUM_PIXELS)) and eyes.current_state is State.OPEN


def test_volume_shows_level_for_three_seconds(eyes, clock):
    eyes.show_volume(Side.BOTH, 3)
    assert lit(eyes) == {0, 1, 2, 3, 12, 13, 14, 15}
    run(eyes, clock, 1, 2999)
    assert eyes.current_anim is Anim.VOLUME
    run(eyes, clock, 3, 1)
    assert eyes.current_anim is Anim.NONE and lit(eyes) == set(range(NUM_PIXELS))


def test_timed_spin_turns_off_when_done(eyes, clock):
    eyes.timed_spin(200)
    run(eyes, clock, 2, 60)
    assert eyes.current_anim is Anim.TIMEDSPIN
    run(eyes, clock, 2, 60)
    assert lit(eyes) == set() and eyes.current_anim is Anim.NONE


def test_off_and_single_side_set(eyes):
    eyes.off()
    assert lit(eyes) == set()
    eyes.set(Side.LEFT, RED)
    assert lit(eyes) == set(range(12, 24))
    eyes.set(Side.UP, RED)
    assert lit(eyes) == set()


def test_side_parse_defaults_to_both():
    assert Side.parse("l") is Side.LEFT and Side.parse("?") is Side.BOTH and Side.parse("") is Side.BOTH
