"use strict";

// Geometry of the Mark 1 front plate in canvas units. The mouth is 32x8 LEDs
// below two 12-LED NeoPixel rings. Firmware pixels 0-11 are the ring it calls
// RIGHT and 12-23 the ring it calls LEFT; we draw them on the viewer's right
// and left respectively (change RING_X to flip).
const MOUTH_COLS = 32;
const MOUTH_ROWS = 8;
const MOUTH_PITCH = 16;
const MOUTH_ORIGIN = { x: 72, y: 190 };
const MOUTH_LED_RADIUS = 6;
const RING_X = [480, 160];
const RING_Y = 100;
const RING_RADIUS = 48;
const EYE_LED_RADIUS = 9;
const RING_SIZE = 12;
const TOP_ANGLE_DEG = 90;
const STEP_ANGLE_DEG = 360 / RING_SIZE;
const MAX_BRIGHTNESS = 30;

const COLORS = {
  plate: "#0d0d10",
  mouthOff: "#1a1a1f",
  mouthOn: "#f4f1e8",
  eyeOff: "#17171b",
};

const canvas = document.getElementById("faceplate");
const ctx = canvas.getContext("2d");
let latest = null;

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

function dot(x, y, radius, color, glow) {
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.shadowBlur = glow ? radius * 2.5 : 0;
  ctx.shadowColor = glow ? color : "transparent";
  ctx.fillStyle = color;
  ctx.fill();
  ctx.shadowBlur = 0;
}

function drawMouth(rows) {
  for (let y = 0; y < MOUTH_ROWS; y++) {
    for (let x = 0; x < MOUTH_COLS; x++) {
      const lit = rows[y][x] === "1";
      dot(MOUTH_ORIGIN.x + x * MOUTH_PITCH, MOUTH_ORIGIN.y + y * MOUTH_PITCH, MOUTH_LED_RADIUS,
        lit ? COLORS.mouthOn : COLORS.mouthOff, lit);
    }
  }
}

function drawEyes(pixels, level) {
  const factor = brightnessFactor(level);
  pixels.forEach((rgb, index) => {
    const lit = rgb.some((c) => c > 0);
    const { x, y } = eyeCenter(index);
    dot(x, y, EYE_LED_RADIUS, lit ? rgbCss(rgb, factor) : COLORS.eyeOff, lit);
  });
}

function render(state) {
  ctx.fillStyle = COLORS.plate;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  drawEyes(state.eyes, state.brightness);
  drawMouth(state.mouth);
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
    latest = JSON.parse(event.data);
    render(latest);
    updateStatus(latest);
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

let knobAngle = 0;
function turnKnob(up) {
  knobAngle += up ? 30 : -30;
  document.querySelector(".knob-face").style.transform = `rotate(${knobAngle}deg)`;
  send({ type: "knob", direction: up ? "up" : "down" });
}

function pressButton() {
  const el = document.getElementById("button");
  el.classList.add("pressed");
  setTimeout(() => el.classList.remove("pressed"), 120);
  send({ type: "button" });
}

document.getElementById("button").addEventListener("click", pressButton);
document.getElementById("knob-up").addEventListener("click", () => turnKnob(true));
document.getElementById("knob-down").addEventListener("click", () => turnKnob(false));
document.getElementById("knob").addEventListener("wheel", (e) => {
  e.preventDefault();
  turnKnob(e.deltaY < 0);
}, { passive: false });
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "BUTTON" && e.key === " ") return;
  if (e.key === " ") { e.preventDefault(); pressButton(); }
  if (e.key === "ArrowUp" || e.key === "ArrowRight") turnKnob(true);
  if (e.key === "ArrowDown" || e.key === "ArrowLeft") turnKnob(false);
});

render({ mouth: Array(MOUTH_ROWS).fill("0".repeat(MOUTH_COLS)), eyes: Array(24).fill([0, 0, 0]), brightness: 30 });
