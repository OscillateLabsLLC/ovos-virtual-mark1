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

// The classic Mycroft weather skill "sunny" icon: 8x8, drawn left of the temperature.
const SUN_ICON = "IICEIBMDNLMDIBCEAA";

const $ = (id) => document.getElementById(id);

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
  };
  for (const [id, fn] of Object.entries(actions)) $(id).addEventListener("click", fn);
}

function bindMouth() {
  const sendText = () => publish("enclosure.mouth.text", { text: $("mouth-text").value });
  $("mouth-text-send").addEventListener("click", sendText);
  $("mouth-text").addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(); });
  $("viseme").addEventListener("change", (e) => publish("enclosure.mouth.viseme", { code: e.target.value }));
  $("icon-send").addEventListener("click", () =>
    publish("enclosure.mouth.display", { img_code: ICONS[$("icon-name").value], xOffset: 0, yOffset: 0, clearPrev: "true" }));
  const actions = {
    "mouth-talk": () => publish("enclosure.mouth.talk"),
    "mouth-listen": () => publish("enclosure.mouth.listen"),
    "mouth-think": () => publish("enclosure.mouth.think"),
    "mouth-smile": () => publish("enclosure.mouth.smile"),
    "mouth-reset": () => publish("enclosure.mouth.reset"),
  };
  for (const [id, fn] of Object.entries(actions)) $(id).addEventListener("click", fn);
}

function bindDemos() {
  const speak = () => publish("speak", { utterance: $("speak-text").value });
  $("speak-send").addEventListener("click", speak);
  $("speak-text").addEventListener("keydown", (e) => { if (e.key === "Enter") speak(); });
  $("demo-weather").addEventListener("click", () =>
    publish("enclosure.weather.display", { temp: $("weather-temp").value, img_code: SUN_ICON }));
  $("demo-date").addEventListener("click", () => publish("ovos.mk1.display_date"));
  $("demo-time").addEventListener("click", () => {
    const now = new Date();
    const text = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;
    publish("ovos.mk1.display_time", { text });
  });
  $("demo-blink-led").addEventListener("click", () => publish("enclosure.system.blink", { times: 3 }));
  $("demo-stop").addEventListener("click", () => publish("mycroft.stop"));
  const sendSerial = () => {
    window.faceplateSend({ type: "serial", line: $("serial-line").value });
    $("serial-line").select();
  };
  $("serial-send").addEventListener("click", sendSerial);
  $("serial-line").addEventListener("keydown", (e) => { if (e.key === "Enter") sendSerial(); });
}

window.updatePanel = (state) => {
  const bus = $("bus");
  bus.textContent = state.bus_connected ? "bus: connected" : "bus: not connected";
  bus.className = "pill " + (state.bus_connected ? "on" : "off");
  $("panel").classList.toggle("offline", !state.bus_connected);
};

fillIcons();
bindEyes();
bindMouth();
bindDemos();
