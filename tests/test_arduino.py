from ovos_virtual_mark1.arduino import BANNER, VERSION_REPLY, VirtualArduino
from ovos_virtual_mark1.eyes import Anim, Side
from ovos_virtual_mark1.mouth import MouthState


def drain(arduino: VirtualArduino) -> list[str]:
    lines, arduino.outbox[:] = list(arduino.outbox), []
    return lines


def test_every_line_is_echoed_and_version_is_answered(arduino):
    arduino.handle_line("system.version")
    assert drain(arduino) == ["Command: system.version", VERSION_REPLY]
    arduino.handle_line("version")
    assert drain(arduino) == ["Command: version", VERSION_REPLY]
    arduino.handle_line("nonsense.thing")
    assert drain(arduino) == ["Command: nonsense.thing"]


def test_connect_sends_boot_banner(arduino):
    arduino.on_connect()
    assert drain(arduino) == [BANNER]


def test_mouth_commands(arduino):
    arduino.handle_line("mouth.text=HI")
    assert arduino.mouth.state is MouthState.TEXT and arduino.mouth.text == "HI"
    arduino.handle_line("mouth.listen")
    assert arduino.mouth.state is MouthState.LISTEN
    arduino.handle_line("mouth.think")
    assert arduino.mouth.state is MouthState.THINK
    arduino.handle_line("mouth.viseme=3")
    assert arduino.mouth.state is MouthState.VISEME
    arduino.handle_line("mouth.faketalk")
    assert arduino.mouth.state is MouthState.TALK
    arduino.handle_line("mouth.reset")
    assert arduino.mouth.state is MouthState.NONE


def test_eyes_commands(arduino):
    arduino.handle_line("eyes.color=33023")
    assert set(arduino.eyes.pixels) == {33023}
    arduino.handle_line("eyes.level=5")
    assert arduino.eyes.bright == 5 and "update" in arduino.outbox and "5" in arduino.outbox
    arduino.handle_line("eyes.blink=l")
    assert arduino.eyes.current_anim is Anim.BLINK and arduino.eyes.current_side is Side.LEFT
    arduino.handle_line("eyes.spin=500")
    assert arduino.eyes.current_anim is Anim.TIMEDSPIN
    arduino.handle_line("eyes.fill=3")
    assert [bool(c) for c in arduino.eyes.pixels[:5]] == [True, True, True, True, False]
    arduino.handle_line("eyes.set=7,255")
    assert arduino.eyes.pixels[7] == 255
    arduino.handle_line("eyes.volume=2")
    assert arduino.eyes.current_anim is Anim.VOLUME
    arduino.handle_line("eyes.off")
    assert not any(arduino.eyes.pixels)
    arduino.handle_line("eyes.on")
    assert all(arduino.eyes.pixels)
    arduino.handle_line("eyes.look=u")
    assert arduino.eyes.current_anim is Anim.LOOK and arduino.eyes.current_side is Side.UP
    arduino.handle_line("eyes.reset")
    assert arduino.eyes.current_anim is Anim.NONE and all(arduino.eyes.pixels)


def test_system_flags_and_led(arduino, clock):
    arduino.handle_line("system.mute")
    assert arduino.snapshot()["muted"] is True
    arduino.handle_line("system.unmute")
    assert arduino.snapshot()["muted"] is False
    arduino.handle_line("system.blink=2")
    assert arduino.snapshot()["led"] is True
    clock.advance(500)
    assert arduino.snapshot()["led"] is False
    clock.advance(500)
    assert arduino.snapshot()["led"] is True
    clock.advance(1000)
    assert arduino.snapshot()["led"] is False


def test_system_reset_reboots(arduino):
    arduino.handle_line("system.mute")
    arduino.handle_line("mouth.text=HI")
    arduino.handle_line("system.reset")
    assert arduino.outbox[-1] == BANNER
    assert arduino.system.muted is False
    assert arduino.mouth.state is MouthState.NONE
    assert arduino.eyes.current_anim is Anim.SPIN


def test_weather_draws_icon_and_temperature(arduino):
    arduino.handle_line("weather.display=72,BIBA")
    lit = arduino.mouth.matrix.lit()
    assert (0, 0) in lit
    assert any(x >= 16 for x, _ in lit)
    assert arduino.mouth.state is MouthState.ICON
    arduino.handle_line("weather.display=-12,BIBA")
    assert min(x for x, _ in arduino.mouth.matrix.lit() if x > 0) == 13


def test_tick_stops_boot_spin_once_mouth_is_busy(arduino, clock):
    arduino.tick()
    assert arduino.eyes.current_anim is Anim.SPIN
    arduino.handle_line("mouth.talk")
    arduino.tick()
    assert arduino.eyes.current_anim is Anim.REFILL


def test_physical_inputs_emit_serial_events(arduino):
    arduino.press_button()
    arduino.turn_knob(clockwise=True)
    arduino.turn_knob(clockwise=False)
    assert drain(arduino) == ["mycroft.stop", "volume.up", "volume.down"]


def test_snapshot_shape(arduino):
    snap = arduino.snapshot()
    assert len(snap["mouth"]) == 8 and all(len(row) == 32 for row in snap["mouth"])
    assert len(snap["eyes"]) == 24 and all(len(rgb) == 3 for rgb in snap["eyes"])
    assert snap["firmware"] == "1.4.2" and snap["brightness"] == 30
    assert snap["eyes_anim"] == "spin" and snap["mouth_state"] == "none"
