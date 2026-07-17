import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const appUrl = process.env.DEMO_URL || "http://127.0.0.1:5173";
const debugPort = Number(process.env.DEMO_DEBUG_PORT || 9777);
const framesDir = path.join(root, ".demo-frames");
const publicDir = path.join(root, "public");
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

if (!fs.existsSync(chromePath)) {
  throw new Error("Google Chrome is required to capture the demo");
}

fs.rmSync(framesDir, { recursive: true, force: true });
fs.mkdirSync(framesDir, { recursive: true });
fs.mkdirSync(publicDir, { recursive: true });

const browser = spawn(
  chromePath,
  [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=/tmp/work-distill-capture-${process.pid}`,
    "--window-size=1440,900",
    "--force-device-scale-factor=1",
    appUrl,
  ],
  { stdio: "ignore" },
);

const cleanup = () => browser.kill("SIGTERM");
process.on("exit", cleanup);

async function waitForPage() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/list`);
      const pages = await response.json();
      const page = pages.find((entry) => entry.type === "page" && entry.url.startsWith(appUrl));
      if (page) return page;
    } catch {
      // Chrome is still starting.
    }
    await wait(100);
  }
  throw new Error("Timed out waiting for the demo page");
}

const page = await waitForPage();
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

let commandId = 0;
const pending = new Map();
socket.addEventListener("message", (messageEvent) => {
  const message = JSON.parse(messageEvent.data);
  if (!message.id || !pending.has(message.id)) return;
  const item = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) item.reject(new Error(message.error.message));
  else item.resolve(message.result);
});

const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++commandId;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });

const evaluate = (expression) =>
  send("Runtime.evaluate", { expression, returnByValue: true });

async function evaluateChecked(expression, message) {
  const result = await evaluate(expression);
  if (result.result?.value === false) throw new Error(message);
  return result;
}

let frameIndex = 0;
async function captureFrame() {
  const result = await send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  const file = path.join(framesDir, `frame-${String(frameIndex).padStart(4, "0")}.png`);
  fs.writeFileSync(file, Buffer.from(result.data, "base64"));
  frameIndex += 1;
  return file;
}

async function captureFor(frameCount, delay = 180) {
  for (let index = 0; index < frameCount; index += 1) {
    await captureFrame();
    await wait(delay);
  }
}

await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: 1440,
  height: 900,
  deviceScaleFactor: 1,
  mobile: false,
  screenWidth: 1440,
  screenHeight: 900,
});
await send("Page.reload", { ignoreCache: true });
await wait(800);

const overview = await captureFrame();
fs.copyFileSync(overview, path.join(publicDir, "demo-overview.png"));
await captureFor(7);

await evaluateChecked(
  '(() => { const button = document.querySelectorAll(".quick-actions button")[1]; if (!button) return false; button.click(); return true; })()',
  "Replay control was not found",
);
await captureFor(30);

await evaluate("window.scrollTo(0, 0)");
const results = await captureFrame();
fs.copyFileSync(results, path.join(publicDir, "demo-results.png"));

await evaluateChecked(
  '(() => { const button = document.querySelectorAll(".view-tabs button")[1]; if (!button) return false; button.click(); return true; })()',
  "Technical tab was not found",
);
await wait(500);
await evaluate(
  'window.scrollTo(0, 0); document.querySelectorAll("*").forEach((node) => { if (node.scrollTop) node.scrollTop = 0; })',
);
const technical = await captureFrame();
fs.copyFileSync(technical, path.join(publicDir, "demo-technical.png"));
await captureFor(12);

await evaluateChecked(
  '(() => { const disclosure = document.querySelector(".console-disclosure"); if (!disclosure) return false; disclosure.click(); return true; })()',
  "Technical disclosure was not found",
);
await captureFor(10);

socket.close();
cleanup();

execFileSync(
  "ffmpeg",
  [
    "-y",
    "-loglevel",
    "error",
    "-framerate",
    "5",
    "-i",
    path.join(framesDir, "frame-%04d.png"),
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    "20",
    "-pix_fmt",
    "yuv420p",
    "-r",
    "30",
    "-movflags",
    "+faststart",
    "-vf",
    "pad=ceil(iw/2)*2:ceil(ih/2)*2",
    path.join(publicDir, "work-distill-demo.mp4"),
  ],
  { stdio: "inherit" },
);

console.log(`Captured ${frameIndex} frames`);
console.log(path.join(publicDir, "demo-overview.png"));
console.log(path.join(publicDir, "demo-results.png"));
console.log(path.join(publicDir, "demo-technical.png"));
console.log(path.join(publicDir, "work-distill-demo.mp4"));
