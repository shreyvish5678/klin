import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import WebSocket from "ws";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const chromePath = [
  process.env.CHROME_BIN,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean).find((candidate) => fs.existsSync(candidate));
const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitForJson(url, timeout = 10_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
    } catch {
      // The local process is still starting.
    }
    await wait(100);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function connectToPage(debugPort, appUrl) {
  const pages = await waitForJson(`http://127.0.0.1:${debugPort}/json/list`);
  const page = pages.find((candidate) => candidate.type === "page" && candidate.url.startsWith(appUrl));
  assert.ok(page, "Work Distill browser page is available");

  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });

  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", (messageEvent) => {
    const message = JSON.parse(messageEvent.data);
    if (!message.id || !pending.has(message.id)) return;
    const entry = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) entry.reject(new Error(message.error.message));
    else entry.resolve(message.result);
  });

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const messageId = ++id;
      pending.set(messageId, { resolve, reject });
      socket.send(JSON.stringify({ id: messageId, method, params }));
    });
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  };
  const waitForValue = async (expression, expected, timeout = 8_000) => {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const value = await evaluate(expression);
      if (value === expected) return value;
      await wait(100);
    }
    throw new Error(`Timed out waiting for browser value: ${expression}`);
  };

  return { socket, send, evaluate, waitForValue };
}

test(
  "browser UI preserves consumer workflow clarity, branch evidence, mobile switching, and keyboard controls",
  { timeout: 35_000 },
  async (context) => {
    if (!fs.existsSync(chromePath)) {
      context.skip("Google Chrome is not installed");
      return;
    }

    const suffix = process.pid % 500;
    const appPort = 5600 + suffix;
    const debugPort = 9600 + suffix;
    const appUrl = `http://127.0.0.1:${appPort}`;
    const server = spawn(process.execPath, ["server.mjs"], {
      cwd: root,
      env: { ...process.env, PORT: String(appPort) },
      stdio: "ignore",
    });
    const browser = spawn(
      chromePath,
      [
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        `--remote-debugging-port=${debugPort}`,
        `--user-data-dir=/tmp/work-distill-ui-test-${process.pid}`,
        "--window-size=390,844",
        "--force-device-scale-factor=1",
        appUrl,
      ],
      { stdio: "ignore" },
    );
    context.after(() => {
      browser.kill("SIGTERM");
      server.kill("SIGTERM");
    });

    await waitForJson(`${appUrl}/api/health`);
    const { socket, send, evaluate, waitForValue } = await connectToPage(debugPort, appUrl);
    context.after(() => socket.close());
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
      screenWidth: 390,
      screenHeight: 844,
    });
    await send("Page.reload", { ignoreCache: true });
    await waitForValue('document.querySelectorAll(".journey-card").length', 5, 15_000);

    assert.deepEqual(
      JSON.parse(await evaluate("JSON.stringify([innerWidth, document.documentElement.scrollWidth])")),
      [390, 390],
    );
    assert.equal(await evaluate('document.querySelectorAll(".flow-connectors").length'), 0);
    assert.equal(await evaluate('document.querySelectorAll(".journey-card").length'), 5);
    assert.equal(
      await evaluate('document.querySelector(".loop-header h3").textContent.trim()'),
      "Latest report + sealed comparison",
    );
    assert.equal(
      await evaluate('document.querySelector(".latest-report dd").textContent.trim()'),
      "9/9",
    );
    assert.match(
      await evaluate('document.querySelector(".latest-report-title span").textContent.trim()'),
      /VERIFICATION PENDING/,
    );
    assert.equal(
      await evaluate('document.querySelector(".latest-activity > span:nth-of-type(2)").textContent.trim()'),
      "Waiting to start",
    );
    assert.equal(
      await evaluate('document.querySelectorAll(".phase-dots > span").length'),
      6,
    );
    assert.equal(
      await evaluate('document.querySelectorAll(".mobile-view-switch button")[0].textContent.trim()'),
      "Start",
    );
    assert.equal(
      await evaluate('document.querySelector(".send-button.start").textContent.includes("Replay 10×")'),
      true,
    );
    assert.equal(
      await evaluate('getComputedStyle(document.querySelector(".composer-hint")).display'),
      "none",
    );

    assert.equal(await evaluate('document.querySelectorAll(".quick-actions button").length'), 2);
    await evaluate('document.querySelectorAll(".quick-actions button")[1].click()');
    await waitForValue(
      'document.querySelector(".run-state strong").textContent.toLowerCase().includes("working")',
      true,
    );
    await evaluate('document.querySelectorAll(".mobile-view-switch button")[1].click()');
    await waitForValue('document.querySelectorAll(".branch-card.running").length', 3);
    assert.equal(
      await evaluate('document.querySelectorAll(".mobile-view-switch button")[1].getAttribute("aria-pressed")'),
      "true",
    );

    assert.equal(await evaluate('document.querySelectorAll(".branch-card.running").length'), 3);
    assert.equal(
      await evaluate('document.querySelector(".phase-rail-label").textContent.trim()'),
      "Step 4 of 6",
    );
    assert.equal(
      await evaluate('getComputedStyle(document.querySelector(".mobile-scroll-hint")).display'),
      "block",
    );
    assert.deepEqual(
      JSON.parse(
        await evaluate(
          'JSON.stringify([...document.querySelectorAll(".branch-card > strong")].map((node) => node.textContent.trim()))',
        ),
      ),
      ["Hosted control", "Untouched Bonsai", "p42 LoRA candidate"],
    );
    assert.equal(
      await evaluate('getComputedStyle(document.querySelector(".branch-card > strong")).fontSize'),
      "16px",
    );
    assert.match(
      await evaluate(
        'getComputedStyle(document.querySelector(".branch-card.running .approach-progress"), "::after").animationName',
      ),
      /approach-runner/,
    );
    assert.equal(
      await evaluate('document.querySelector(".console-disclosure").getAttribute("aria-expanded")'),
      "false",
    );
    await evaluate('document.querySelector(".console-disclosure").click()');
    assert.equal(
      await evaluate('document.querySelector(".console-disclosure").getAttribute("aria-expanded")'),
      "true",
    );
    assert.equal(await evaluate('document.querySelectorAll(".console-tabs button").length'), 3);
    await evaluate('document.querySelector(".console-disclosure").click()');

    await waitForValue(
      'document.querySelectorAll(".branch-card")[2].classList.contains("rejected")',
      true,
    );
    assert.equal(await evaluate('document.querySelectorAll(".branch-card")[2].classList.contains("rejected")'), true);
    assert.equal(
      await evaluate(
        'document.querySelectorAll(".branch-card")[2].querySelector(".status-mark").getAttribute("aria-label")',
      ),
      "rejected",
    );
    await evaluate('document.querySelectorAll(".branch-card")[2].click()');
    assert.deepEqual(
      JSON.parse(
        await evaluate(
          'JSON.stringify([...document.querySelectorAll(".flow-detail-drawer dd")].map((node) => node.textContent.trim()))',
        ),
      ),
      ["Not selected", "0 / 9", "Bonsai 27B Q1 + p42", "branches/p42/rejection.json", "01 / 01"],
    );
    await evaluate('document.querySelector(".flow-detail-drawer button").click()');

    await evaluate('document.querySelectorAll(".view-tabs button")[2].click()');
    assert.equal(await evaluate('document.querySelector(".inventory-agent-button").tagName'), "BUTTON");
    assert.equal(await evaluate('document.querySelector(".inventory-agent-button").disabled'), true);
    assert.equal(
      await evaluate('getComputedStyle(document.querySelector(".mobile-stop-button")).display !== "none"'),
      true,
    );
    await evaluate('document.querySelector(".mobile-stop-button").click()');
    assert.match(await evaluate('document.querySelector(".run-state strong").textContent'), /stopped/i);
    await waitForValue('document.querySelector(".inventory-agent-button").disabled', false);

    await send("Page.reload", { ignoreCache: true });
    await waitForValue('document.querySelectorAll(".journey-card").length', 5, 15_000);
    await evaluate('document.querySelectorAll(".quick-actions button")[1].click()');
    await evaluate('document.querySelectorAll(".mobile-view-switch button")[1].click()');
    await waitForValue(
      'document.querySelector(".run-state strong").textContent.trim()',
      "Complete",
      15_000,
    );
    assert.equal(
      await evaluate('document.querySelector(".recommendation-card strong").textContent.trim()'),
      "Prior sealed decision: NOT YET",
    );
    assert.equal(
      await evaluate('document.querySelectorAll(".branch-card.recommended").length'),
      0,
    );
    await evaluate('document.querySelector(".review-proposal-button").click()');
    assert.equal(
      await evaluate('document.querySelector(".flow-detail-drawer .drawer-head span").textContent.trim()'),
      "PATH C",
    );
    assert.equal(
      await evaluate('document.querySelector(".flow-detail-drawer .drawer-head strong").textContent.trim()'),
      "p42 LoRA candidate",
    );
    await evaluate('document.querySelector(".console-disclosure").click()');
    await evaluate('document.querySelectorAll(".console-tabs button")[2].click()');
    assert.match(
      await evaluate('document.querySelector(".metrics-note span").textContent.trim()'),
      /9\/9 · 20 S/,
    );
    assert.equal(
      await evaluate(
        'document.querySelector(".metric-comparison > div:nth-child(2) strong:last-child").textContent.trim()',
      ),
      "9 / 9",
    );
  },
);
