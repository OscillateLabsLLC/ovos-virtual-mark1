"use strict";

// Control panel: every control publishes a message on the OVOS bus so the real
// PHAL plugin drives the faceplate, exactly as a skill would. The raw serial box
// bypasses the bus and feeds a line straight to the virtual Arduino.

// Encoded with ovos-mark1-utils (ovos_mark1.faceplate.icons, invert=True).
const ICONS = {
  Music: "aIAAAAAAAAAAAAAAAAAAAAAAAAAEAOOHGAGEGOOHAAAAAAAAAAAAAAAAAAAAAAAAAA",
  Heart: "aIAAAAAAAAAAAAAAAAAAAAAAMAOBODMHIPMHODOBMAAAAAAAAAAAAAAAAAAAAAAAAA",
  "Hollow heart": "aIAAAAAAAAAAAAAAAAAAAAAAMACBCCEEIIEECCCBMAAAAAAAAAAAAAAAAAAAAAAAAA",
  Warning: "aIAAAAAAAAAAAAAAAAAIAMAOAPIPMPGKDCGKMPIPAPAOAMAIAAAAAAAAAAAAAAAAAA",
  Info: "aIAAAAAAAAAAAAAAAAAAAAAAAAAAAAABGPGPGPAIAAAAAAAAAAAAAAAAAAAAAAAAAA",
  Plus: "aIAAAAAAAAAAAAAAAAAAAAAAAAAAIDIDOPOPOPIDIDAAAAAAAAAAAAAAAAAAAAAAAA",
  Cross: "aIAAAAAAAAAAAAAAAAAAAAAAAAEEOOMGIDABIDMGOOEEAAAAAAAAAAAAAAAAAAAAAA",
  Skull: "aIAAAAAAAAAAAAAAAAAAAAAAMAKBKPODOOODKPKBMAAAAAAAAAAAAAAAAAAAAAAAAA",
  Boat: "aIAAAAAAAAAAAAAAAAAAABACAGIEMEOEPHAEAGACABABAAAAAAAAAAAAAAAAAAAAAA",
  "Space invader": "aIAAAAAAAAAAAAAAAAAAAAMGECECOCPDLDPDLDPDOCECECMGAAAAAAAAAAAAAAAAAA",
  "Arrow left": "aIAAAAAAAAAAAAAAAAAAAAABIDMHOOGNKLIDIDIDIDIDIDAAAAAAAAAAAAAAAAAAAA",
};

// Eye colour presets: the plugin's boot blue, the firmware default tan, and a spread of hues.
const SWATCHES = {
  "OVOS blue": "#0000ff", "Mark 1 tan": "#706569", White: "#ffffff", Green: "#00c850",
  Amber: "#ffa000", Red: "#ff2020", Purple: "#a000ff", Cyan: "#00d0ff",
};
// Classic 8x8 Mark 1 weather icons, indexed by the plugin's condition code.
const WEATHER_ICONS = ["IICEIBMDNLMDIBCEAA", "IIEEGBGDHLHDHBGEEA", "IIIBMDMDODODODMDIB", "IIMAOJOFPBPJPFOBMA",
  "IIMIOFOBPFPDPJOFMA", "IIAAIIMEODLBJAAAAA", "IIJEKCMBPHMBKCJEAA", "IIABIBIBIJIJJGJAGA"];
const RESET_SETTLE_MS = 60;

const DAY_NAMES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const MONTH_NAMES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

const VISEMES = ["0 wide open", "1 pursed", "2 open", "3 narrow lips", "4 closed", "5 parted", "6 barely open"];
const STATIC_MOUTH_STATES = new Set(["text", "icon"]);

const $ = (id) => document.getElementById(id);
let mouthState = "none";

function publish(msgType, data = {}) {
  window.faceplateSend({ type: "bus", msg_type: msgType, data });
}

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function side() {
  return $("eye-side").value;
}

function fillIcons() {
  const select = $("icon-name");
  for (const name of Object.keys(ICONS)) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
}

function fillSwatches() {
  const holder = $("swatches");
  for (const [name, hex] of Object.entries(SWATCHES)) {
    const b = document.createElement("button");
    b.className = "swatch";
    b.title = name;
    b.style.background = hex;
    b.addEventListener("click", () => {
      $("eye-color").value = hex;
      publish("enclosure.eyes.color", hexToRgb(hex));
    });
    holder.appendChild(b);
  }
}

function bindEyes() {
  $("eye-color").addEventListener("input", (e) => publish("enclosure.eyes.color", hexToRgb(e.target.value)));
  $("eye-level").addEventListener("change", (e) => {
    $("eye-level-value").textContent = e.target.value;
    publish("enclosure.eyes.level", { level: Number(e.target.value) });
  });
  $("eye-level").addEventListener("input", (e) => { $("eye-level-value").textContent = e.target.value; });
  $("eye-fill").addEventListener("change", (e) => publish("enclosure.eyes.fill", { percentage: Number(e.target.value) }));
  $("eye-volume").addEventListener("change", (e) => publish("enclosure.eyes.volume", { volume: Number(e.target.value) }));
  const actions = {
    "eye-blink": () => publish("enclosure.eyes.blink", { side: side() }),
    "eye-narrow": () => publish("enclosure.eyes.narrow"),
    "eye-look": () => publish("enclosure.eyes.look", { side: side() }),
    "eye-spin": () => publish("enclosure.eyes.spin"),
    "eye-timedspin": () => publish("enclosure.eyes.timedspin", { length: 3000 }),
    "eye-on": () => publish("enclosure.eyes.on"),
    "eye-off": () => publish("enclosure.eyes.off"),
    "eye-reset": () => publish("enclosure.eyes.reset"),
    "eye-setpixel": () => publish("enclosure.eyes.setpixel", { idx: Number($("eye-pixel").value), ...hexToRgb($("eye-color").value) }),
  };
  for (const [id, fn] of Object.entries(actions)) $(id).addEventListener("click", fn);
}

// The firmware refuses a viseme while text or an icon is showing (MycroftMouth::viseme),
// so clear the mouth first in that case, then send the shape once the reset has landed.
function showViseme(code) {
  if (STATIC_MOUTH_STATES.has(mouthState)) {
    publish("enclosure.mouth.reset");
    setTimeout(() => publish("enclosure.mouth.viseme", { code }), RESET_SETTLE_MS * 2);
  } else {
    publish("enclosure.mouth.viseme", { code });
  }
}

function bindMouth() {
  const sendText = () => publish("enclosure.mouth.text", { text: $("mouth-text").value });
  $("mouth-text-send").addEventListener("click", sendText);
  $("mouth-text").addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(); });
  VISEMES.forEach((label, code) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.addEventListener("click", () => showViseme(String(code)));
    $("visemes").appendChild(b);
  });
  $("icon-send").addEventListener("click", () =>
    publish("enclosure.mouth.display", { img_code: ICONS[$("icon-name").value], xOffset: 0, yOffset: 0, clearPrev: "true" }));
  const actions = {
    "mouth-talk": () => publish("enclosure.mouth.talk"),
    "mouth-listen": () => publish("enclosure.mouth.listen"),
    "mouth-think": () => publish("enclosure.mouth.think"),
    "mouth-reset": () => publish("enclosure.mouth.reset"),
    "mouth-events": () => publish("enclosure.mouth.events.activate"),
    "mouth-events-off": () => publish("enclosure.mouth.events.deactivate"),
  };
  for (const [id, fn] of Object.entries(actions)) $(id).addEventListener("click", fn);
}

function bindDemos() {
  const speak = () => publish("speak", { utterance: $("speak-text").value });
  $("speak-send").addEventListener("click", speak);
  $("speak-text").addEventListener("keydown", (e) => { if (e.key === "Enter") speak(); });
  $("demo-weather").addEventListener("click", () =>
    publish("enclosure.weather.display", { temp: $("weather-temp").value, img_code: Number($("weather-code").value) }));
  $("demo-weather-direct").addEventListener("click", () => {
    const line = `weather.display=${$("weather-temp").value},x=2,${WEATHER_ICONS[Number($("weather-code").value)]}`;
    // A reset first, then a tick, so the firmware's post-animation reset cannot wipe the display.
    window.faceplateSend({ type: "serial", line: "mouth.reset" });
    setTimeout(() => window.faceplateSend({ type: "serial", line }), RESET_SETTLE_MS);
  });
  $("demo-date").addEventListener("click", () => {
    const now = new Date();
    publish("ovos.mk1.display_date", { text: `${DAY_NAMES[now.getDay()]} ${MONTH_NAMES[now.getMonth()]} ${now.getDate()}` });
  });
  $("demo-time").addEventListener("click", () => {
    const now = new Date();
    const text = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;
    publish("ovos.mk1.display_time", { text });
  });
  $("demo-stop").addEventListener("click", () => publish("mycroft.stop"));
  const sendSerial = () => {
    window.faceplateSend({ type: "serial", line: $("serial-line").value });
    $("serial-line").select();
  };
  $("serial-send").addEventListener("click", sendSerial);
  $("serial-line").addEventListener("keydown", (e) => { if (e.key === "Enter") sendSerial(); });
}

// Lifecycle messages. Sleep really puts the listener to sleep (it binds
// SpecMessage.LISTENER_SLEEP); Wake asks the listener to wake, and the listener
// then announces mycroft.awoken, which the plugin animates.
function bindSystem() {
  const actions = {
    "sys-sleep": () => publish("recognizer_loop:sleep"),
    "sys-wake": () => publish("recognizer_loop:wake_up"),
    "sys-no-internet": () => publish("enclosure.notify.no_internet"),
    "sys-reset": () => publish("enclosure.reset"),
    "sys-mute": () => publish("enclosure.system.mute"),
    "sys-unmute": () => publish("enclosure.system.unmute"),
    "sys-blink": () => publish("enclosure.system.blink", { times: Number($("sys-blink-times").value) }),
  };
  for (const [id, fn] of Object.entries(actions)) $(id).addEventListener("click", fn);
}

window.updatePanel = (state) => {
  mouthState = state.mouth_state;
  const bus = $("bus");
  bus.textContent = state.bus_connected ? "bus: connected" : "bus: not connected";
  bus.className = "pill " + (state.bus_connected ? "on" : "off");
  $("panel").classList.toggle("offline", !state.bus_connected);
};

fillIcons();
fillSwatches();
bindEyes();
bindMouth();
bindDemos();
bindSystem();
