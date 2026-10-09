"use strict";

// The faceplate is an inline SVG in the proportions of the Mark 1's front plate.
// The vector styling (silver rim, dark glass, mic grille, ring tracks, LED glow)
// follows Timon's OVOS installer artwork, with thanks. Firmware pixels 0-11 are
// the ring the firmware calls RIGHT and 12-23 the ring it calls LEFT; they are
// drawn on the viewer's right and left (swap RING_X to flip). Ring index 0 sits
// just left of the top and indices run counter-clockwise, which is what makes
// eyes.narrow close from top and bottom.
const SVG_NS = "http://www.w3.org/2000/svg";
const VIEW_BOX = "-4 -4 172.38 65.38";
const RIM_PATH = "M82.19 0C124 0 164.38 3 164.38 28.69S124 57.37 82.19 57.37S0 54.37 0 28.69S40.4 0 82.19 0Z";
const GLASS_PATH = "M82.19 2C123 2 162.38 5 162.38 28.69S123 55.37 82.19 55.37S2 52.37 2 28.69S41.4 2 82.19 2Z";
const REFLECTION_PATH = "M15 10C47 2 115 2 148 11";
const MIC = { cx: 82.19, cy: 10.8, dots: 30, radius: 4.4, dotRadius: 0.46, goldenAngle: 2.399963 };
const RING_X = [140.19, 24.19];
const RING_Y = 28.69;
const RING_RADIUS = 13.5;
const EYE_LED_RADIUS = 1.6;
const RING_SIZE = 12;
const TOP_ANGLE_DEG = 90;
const STEP_ANGLE_DEG = 360 / RING_SIZE;
const MOUTH_COLS = 32;
const MOUTH_ROWS = 8;
const MOUTH_ORIGIN = { x: 43.34, y: 19.84 };
const MOUTH_PITCH = 2.5;
const MOUTH_LED_RADIUS = 0.72;
const MAX_BRIGHTNESS = 30;
const TRACK_ALPHA = 0.09;

const svg = document.getElementById("faceplate");
const eyeLeds = [];
const mouthLeds = [];
const eyeTracks = [];

function el(name, attrs = {}, parent = svg) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  parent.appendChild(node);
  return node;
}

function gradient(defs, id, stops, attrs) {
  const g = el("linearGradient", { id, ...attrs }, defs);
  for (const [offset, color] of stops) el("stop", { offset, "stop-color": color }, g);
}

function eyeCenter(index) {
  const ring = Math.floor(index / RING_SIZE);
  const slot = index % RING_SIZE;
  const theta = ((TOP_ANGLE_DEG + STEP_ANGLE_DEG * (slot + 0.5)) * Math.PI) / 180;
  return { x: RING_X[ring] + RING_RADIUS * Math.cos(theta), y: RING_Y - RING_RADIUS * Math.sin(theta) };
}

function buildFace() {
  svg.setAttribute("viewBox", VIEW_BOX);
  const defs = el("defs");
  gradient(defs, "mark1-rim", [["0", "#fff"], ["1", "#a6b1bd"]], { x2: "0", y2: "1" });
  gradient(defs, "mark1-glass", [["0", "#303940"], ["0.5", "#12191e"], ["1", "#263039"]], { x2: "0.8", y2: "1" });
  el("path", { class: "face-rim", d: RIM_PATH });
  el("path", { class: "face-glass", d: GLASS_PATH });
  el("path", { class: "face-reflection", d: REFLECTION_PATH });
  const grille = el("g", { class: "mic-grille" });
  for (let i = 0; i < MIC.dots; i++) {
    const angle = i * MIC.goldenAngle;
    const r = MIC.radius * Math.sqrt((i + 0.5) / MIC.dots);
    el("circle", { cx: (MIC.cx + Math.cos(angle) * r).toFixed(2), cy: (MIC.cy + Math.sin(angle) * r).toFixed(2), r: MIC.dotRadius }, grille);
  }
  RING_X.forEach((cx) => eyeTracks.push(el("circle", { class: "eye-track", cx, cy: RING_Y, r: RING_RADIUS })));
  const eyes = el("g", { class: "mark1-eyes" });
  for (let i = 0; i < RING_SIZE * 2; i++) {
    const { x, y } = eyeCenter(i);
    eyeLeds.push(el("circle", { class: "eye-led", cx: x.toFixed(3), cy: y.toFixed(3), r: EYE_LED_RADIUS }, eyes));
  }
  const mouth = el("g", { class: "mark1-mouth" });
  for (let i = 0; i < MOUTH_COLS * MOUTH_ROWS; i++) {
    const cx = (MOUTH_ORIGIN.x + (i % MOUTH_COLS) * MOUTH_PITCH).toFixed(2);
    const cy = (MOUTH_ORIGIN.y + Math.floor(i / MOUTH_COLS) * MOUTH_PITCH).toFixed(2);
    mouthLeds.push(el("circle", { class: "mouth-led", cx, cy, r: MOUTH_LED_RADIUS }, mouth));
  }
}

function brightnessFactor(level) {
  return Math.min(1, (level + 1) / (MAX_BRIGHTNESS + 1));
}

function rgbCss([r, g, b], factor, alpha = 1) {
  const c = [r, g, b].map((v) => Math.round(v * factor));
  return `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${alpha})`;
}

function render(state) {
  const factor = brightnessFactor(state.brightness);
  const ringTint = [[0, 0, 0], [0, 0, 0]];
  state.eyes.forEach((rgb, i) => {
    const lit = rgb.some((c) => c > 0);
    const led = eyeLeds[i];
    led.classList.toggle("lit", lit);
    led.style.fill = lit ? rgbCss(rgb, factor) : "";
    led.style.setProperty("--glow", lit ? rgbCss(rgb, 1, 0.9) : "transparent");
    if (lit) ringTint[Math.floor(i / RING_SIZE)] = rgb;
  });
  eyeTracks.forEach((track, ring) => { track.style.stroke = rgbCss(ringTint[ring], 1, TRACK_ALPHA); });
  state.mouth.forEach((row, y) => {
    for (let x = 0; x < MOUTH_COLS; x++) mouthLeds[y * MOUTH_COLS + x].classList.toggle("lit", row[x] === "1");
  });
}

function setPill(id, text, cls) {
  const node = document.getElementById(id);
  node.textContent = text;
  node.className = "pill" + (cls ? " " + cls : "");
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

buildFace();
render({ mouth: Array(MOUTH_ROWS).fill("0".repeat(MOUTH_COLS)), eyes: Array(24).fill([0, 0, 0]), brightness: 30 });
let socket = connect();

function send(event) {
  if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(event));
}
window.faceplateSend = send;

function turnKnob(up) {
  send({ type: "knob", direction: up ? "up" : "down" });
}

function pressButton() {
  const button = document.getElementById("button");
  button.classList.add("pressed");
  setTimeout(() => button.classList.remove("pressed"), 120);
  send({ type: "button" });
}

// The physical knob is the button: click the face to press it, scroll over it for volume.
svg.addEventListener("click", pressButton);
svg.addEventListener("wheel", (e) => {
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
