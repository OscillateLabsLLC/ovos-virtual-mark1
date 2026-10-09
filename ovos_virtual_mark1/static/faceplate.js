"use strict";

// Geometry of the Mark 1 front plate in canvas units, proportioned from the
// product photo: the two 12-LED NeoPixel rings flank the 32x8 mouth on one
// horizontal line, ring diameter about 1.5x the matrix height. Firmware
// pixels 0-11 are the ring it calls RIGHT and 12-23 the ring it calls LEFT;
// we draw them on the viewer's right and left (change RING_X to flip).
const MOUTH_COLS = 32;
const MOUTH_ROWS = 8;
const MOUTH_PITCH = 10;
const MOUTH_ORIGIN = { x: 181, y: 45 };
const MOUTH_LED_RADIUS = 3.6;
const RING_X = [600, 72];
const RING_Y = 80;
const RING_RADIUS = 56;
const EYE_LED_RADIUS = 7;
const RING_SIZE = 12;
const TOP_ANGLE_DEG = 90;
const STEP_ANGLE_DEG = 360 / RING_SIZE;
const MAX_BRIGHTNESS = 30;

// Diffusion through the smoked acrylic: a wide soft halo under a slightly
// blurred copy of the crisp LEDs, then a dark tint so unlit LEDs almost vanish.
const DIFFUSION = { haloBlurPx: 7, haloAlpha: 0.85, ledBlurPx: 1.1, ledAlpha: 0.9, tint: "rgba(4, 4, 8, 0.22)" };

const COLORS = {
  plate: "#07070a",
  mouthOff: "#121216",
  mouthOn: "#f6f3ea",
  eyeOff: "#101014",
};

const canvas = document.getElementById("faceplate");
const ctx = canvas.getContext("2d");
const ledLayer = document.createElement("canvas");
ledLayer.width = canvas.width;
ledLayer.height = canvas.height;
const led = ledLayer.getContext("2d");
const supportsFilter = "filter" in led;

function eyeCenter(index) {
  const ring = Math.floor(index / RING_SIZE);
  const slot = index % RING_SIZE;
  const theta = ((TOP_ANGLE_DEG + STEP_ANGLE_DEG * (slot + 0.5)) * Math.PI) / 180;
  return { x: RING_X[ring] + RING_RADIUS * Math.cos(theta), y: RING_Y - RING_RADIUS * Math.sin(theta) };
}

function brightnessFactor(level) {
  return Math.min(1, (level + 1) / (MAX_BRIGHTNESS + 1));
}

function rgbCss([r, g, b], factor) {
  return `rgb(${Math.round(r * factor)}, ${Math.round(g * factor)}, ${Math.round(b * factor)})`;
}

function dot(g, x, y, radius, color) {
  g.beginPath();
  g.arc(x, y, radius, 0, Math.PI * 2);
  g.fillStyle = color;
  g.fill();
}

function drawMouth(g, rows) {
  for (let y = 0; y < MOUTH_ROWS; y++) {
    for (let x = 0; x < MOUTH_COLS; x++) {
      const lit = rows[y][x] === "1";
      dot(g, MOUTH_ORIGIN.x + x * MOUTH_PITCH, MOUTH_ORIGIN.y + y * MOUTH_PITCH, MOUTH_LED_RADIUS,
        lit ? COLORS.mouthOn : COLORS.mouthOff);
    }
  }
}

function drawEyes(g, pixels, level) {
  const factor = brightnessFactor(level);
  pixels.forEach((rgb, index) => {
    const lit = rgb.some((c) => c > 0);
    const { x, y } = eyeCenter(index);
    dot(g, x, y, EYE_LED_RADIUS, lit ? rgbCss(rgb, factor) : COLORS.eyeOff);
  });
}

function composite() {
  ctx.filter = "none";
  ctx.globalAlpha = 1;
  ctx.fillStyle = COLORS.plate;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (supportsFilter) {
    ctx.filter = `blur(${DIFFUSION.haloBlurPx}px)`;
    ctx.globalAlpha = DIFFUSION.haloAlpha;
    ctx.drawImage(ledLayer, 0, 0);
    ctx.filter = `blur(${DIFFUSION.ledBlurPx}px)`;
  }
  ctx.globalAlpha = DIFFUSION.ledAlpha;
  ctx.drawImage(ledLayer, 0, 0);
  ctx.filter = "none";
  ctx.globalAlpha = 1;
  ctx.fillStyle = DIFFUSION.tint;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function render(state) {
  led.clearRect(0, 0, ledLayer.width, ledLayer.height);
  drawEyes(led, state.eyes, state.brightness);
  drawMouth(led, state.mouth);
  composite();
}

function setPill(id, text, cls) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = "pill" + (cls ? " " + cls : "");
}

function updateStatus(state) {
  setPill("serial", state.serial_connected ? "serial: PHAL connected" : "serial: waiting for PHAL",
    state.serial_connected ? "on" : "off");
  setPill("mouth-state", "mouth: " + state.mouth_state);
  setPill("eyes-anim", "eyes: " + state.eyes_anim);
  setPill("brightness", "eyes level: " + state.brightness);
  setPill("muted", "muted", state.muted ? "off" : "hidden");
  setPill("led", "LED", state.led ? "on" : "hidden");
  setPill("firmware", "fw v" + state.firmware);
  document.getElementById("last-command").textContent = state.last_command ? "> " + state.last_command : "";
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);
    render(state);
    updateStatus(state);
    if (window.updatePanel) window.updatePanel(state);
  };
  ws.onclose = () => {
    setPill("serial", "GUI disconnected, retrying", "off");
    setTimeout(connect, 1000);
  };
  return ws;
}

let socket = connect();

function send(event) {
  if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(event));
}
window.faceplateSend = send;

let knobOffset = 0;
function turnKnob(up) {
  knobOffset += up ? 4 : -4;
  document.querySelector(".knob-face").style.backgroundPosition = `${knobOffset}px 0`;
  send({ type: "knob", direction: up ? "up" : "down" });
}

function pressButton() {
  for (const id of ["knob", "button"]) {
    const el = document.getElementById(id);
    el.classList.add("pressed");
    setTimeout(() => el.classList.remove("pressed"), 120);
  }
  send({ type: "button" });
}

const knob = document.getElementById("knob");
knob.addEventListener("click", pressButton);
knob.addEventListener("wheel", (e) => {
  e.preventDefault();
  turnKnob(e.deltaY < 0);
}, { passive: false });
document.getElementById("button").addEventListener("click", pressButton);
document.getElementById("knob-up").addEventListener("click", () => turnKnob(true));
document.getElementById("knob-down").addEventListener("click", () => turnKnob(false));
// Keyboard shortcuts apply only when nothing editable has focus: typing in the
// panel's inputs must keep its spaces and arrow keys.
const EDITABLE_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT", "BUTTON"]);
document.addEventListener("keydown", (e) => {
  if (EDITABLE_TAGS.has(e.target.tagName) || e.target.isContentEditable) return;
  if (e.key === " ") { e.preventDefault(); pressButton(); }
  if (e.key === "ArrowUp" || e.key === "ArrowRight") turnKnob(true);
  if (e.key === "ArrowDown" || e.key === "ArrowLeft") turnKnob(false);
});
knob.addEventListener("keydown", (e) => {
  if (e.key === " " || e.key === "Enter") { e.preventDefault(); pressButton(); }
});

render({ mouth: Array(MOUTH_ROWS).fill("0".repeat(MOUTH_COLS)), eyes: Array(24).fill([0, 0, 0]), brightness: 30 });
