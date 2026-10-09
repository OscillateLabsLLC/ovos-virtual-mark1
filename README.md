# ovos-virtual-mark1

[![Status: Active](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/OscillateLabsLLC/.github/blob/main/SUPPORT_STATUS.md)
[![Unit Tests](https://github.com/OscillateLabsLLC/ovos-virtual-mark1/actions/workflows/unit_tests.yml/badge.svg)](https://github.com/OscillateLabsLLC/ovos-virtual-mark1/actions/workflows/unit_tests.yml)

A virtual Mycroft Mark 1 faceplate for [OpenVoiceOS](https://openvoiceos.org). It is a
software Arduino that speaks the Mark 1's serial protocol, plus a browser GUI that draws
the 32x8 LED mouth and the two 12-pixel NeoPixel eye rings with the same pixel layout as
the hardware.

The unmodified [`ovos-PHAL-plugin-mk1`](https://github.com/OpenVoiceOS/ovos-PHAL-plugin-mk1)
drives it. No OVOS code changes are needed: the plugin opens its serial port with
pyserial's `serial_for_url`, which accepts a `socket://` URL, so it connects to this
program instead of `/dev/ttyAMA0`.

```
OVOS bus  ──▶  ovos-PHAL-plugin-mk1  ──serial over TCP──▶  ovos-virtual-mark1  ──websocket──▶  browser
            (enclosure.* messages)      (mouth.text=..., eyes.blink=l, ...)     (virtual Arduino)
```

## Fidelity

The mouth and eye behaviour is a port of the
[Mark 1 Arduino firmware](https://github.com/MycroftAI/enclosure-mark1), not an
approximation:

- Fonts (5x4 and 8x4) and every mouth bitmap (listen, talk, think, visemes) are generated
  from the firmware headers by `scripts/port_firmware_tables.py`.
- Text scrolling, centring, the two-part `$` image protocol, the `x=`/`y=`/`cP=` icon
  prefixes, the weather layout, and the eye state machine (blink, narrow, widen, look,
  unlook, spin, timed spin, refill, volume, fill) follow the firmware line by line,
  including its quirks such as the boot spin emptying the ring before a single pixel
  chases around it, and `mouth.faketalk` resting on frame 0.
- Every received line is echoed back as `Command: ...`, `version` is answered with
  `Mycroft Mark 1 v1.4.2`, and a connect sends the boot banner a quarter second later,
  the way the Arduino's DTR auto-reset and bootloader pause do on a real unit. The delay
  also matters because pyserial's socket transport discards anything received while the
  port is being opened.
- The GUI's top button sends `mycroft.stop`; the knob sends `volume.up` / `volume.down`.

Not emulated yet: the long-press hardware menu and the hardware self test. The on-board
LED (`system.blink`) is tracked non-blocking and shown as a status pill; on real hardware
it is inside the case.

## Quick start

Requires Python 3.10+ and a running OVOS install.

```bash
pip install ovos-virtual-mark1          # or: uv tool install ovos-virtual-mark1
ovos-virtual-mark1                      # serial on 127.0.0.1:5555, GUI on http://127.0.0.1:8765
```

Install the Mark 1 PHAL plugin into the same environment as OVOS and point it at the
virtual serial port in `~/.config/mycroft/mycroft.conf`:

```json
{
  "PHAL": {
    "ovos-PHAL-plugin-mk1": {
      "enabled": true,
      "port": "socket://127.0.0.1:5555"
    },
    "ovos-phal-mk1": {
      "enabled": true,
      "port": "socket://127.0.0.1:5555"
    }
  }
}
```

Both keys are needed with plugin 0.2.0a2 and earlier: the plugin's validator reads
`ovos-PHAL-plugin-mk1`, but PHAL hands the constructor the config stored under the
entry-point name `ovos-phal-mk1`. With only the first key the port silently falls back to
`/dev/ttyAMA0`.

Restart PHAL, open the GUI, and talk to OVOS. Listening shows the wave, speech shows the
talk shape, and any skill that uses the enclosure API draws on the mouth. To exercise it
without a skill:

```bash
pip install ovos-mark1-utils
python -c "from ovos_mark1.faceplate.animations import ParticleBox; ParticleBox().run()"
```

### Lip sync

`enclosure.mouth.viseme_list` is only emitted when the TTS plugin returns visemes. Most
modern plugins do not, so the mouth rests on the talk shape during speech. Pair the
faceplate with a fake viseme generator if you want it to move.

## Control panel

Below the faceplate the page has a control panel. Every control publishes a message on
the OVOS messagebus, so the real PHAL plugin reacts exactly as it would to a skill:

- **Eyes**: colour, level (brightness), blink, narrow, look with a side, spin, timed spin,
  on, off, reset, fill percentage, and volume.
- **Mouth**: scrolling text, the seven viseme shapes, a stock icon from `ovos-mark1-utils`,
  and the talk, listen, think, and reset animations. The firmware ignores a viseme while
  text or an icon is showing, so the viseme buttons reset the mouth first in that case.
- **Demos**: `speak` an utterance through TTS, the weather layout with a sky condition,
  date, time, and `mycroft.stop`. "Weather (direct)" sends the same display straight to
  the virtual Arduino with the classic 8x8 icon, because the plugin's own weather path
  sends an icon too large for the firmware (ovos-PHAL-plugin-mk1 issue #55).

Two plugin behaviours to know about. The date and time displays switch mouth animations
off while they are up (ten and five seconds) and the plugin blocks for that long, so
talk, listen and think are ignored meanwhile; the "Re-enable animations" button publishes
`enclosure.mouth.events.activate` if they get stuck. And `enclosure.mouth.smile` does
nothing on any Mark 1: firmware 1.4.2 has no smile handler, its bitmap is commented out.
- **Raw serial**: a line such as `eyes.look=l` fed straight to the virtual Arduino,
  bypassing the bus. Useful when OVOS is not running.

The bus link defaults to `ws://127.0.0.1:8181/core`; change it with `--bus` or disable
it with `--no-bus`. The status row shows whether the bus and the PHAL serial link are up.

### Restart order

The PHAL plugin does not reconnect if the emulator restarts: its serial reader logs
`read failed: socket disconnected` in a loop until PHAL itself is restarted. Start the
emulator first, then PHAL. The same reader behaviour, a retry loop with no backoff or
port reopen, is what a real Mark 1 shows when its UART hiccups.

## Options

```
ovos-virtual-mark1 [--host 127.0.0.1] [--serial-port 5555] [--http-port 8765]
                   [--bus ws://127.0.0.1:8181/core | --no-bus] [-v]
```

`GET /state` returns the current faceplate as JSON. The websocket at `/ws` streams it on
every change and accepts `{"type": "button"}`, `{"type": "knob", "direction": "up"|"down"}`,
`{"type": "serial", "line": "..."}` and `{"type": "bus", "msg_type": "...", "data": {...}}`.

## Geometry notes

Firmware pixels 0 to 11 are the ring the firmware calls RIGHT and 12 to 23 the ring it
calls LEFT; the GUI draws them on the viewer's right and left. Ring index 0 sits just
left of the top of the ring and indices increase counter-clockwise, which is what makes
`eyes.narrow` close from the top and bottom and `eyes.look=l` leave three pixels lit on
the left. Flip `RING_X` in `static/faceplate.js` if your unit disagrees.

## Development

```bash
uv sync --extra test
uv run pytest
uv run ruff check .
uv run ovos-virtual-mark1 -v
```

`just` recipes exist for each of these. To refresh the firmware tables:

```bash
git clone https://github.com/MycroftAI/enclosure-mark1
just port-tables ./enclosure-mark1
```

## Credits

The faceplate's vector styling, the silver rim, dark glass, mic grille, ring tracks and
LED glow, follows Timon's Mark 1 artwork for the OVOS installer wizard, used with thanks.
The firmware tables are derived from Mycroft AI's Apache-2.0 licensed enclosure firmware.

## License

Apache-2.0. The fonts and mouth bitmaps are derived from the Apache-2.0 licensed
Mycroft AI firmware.
