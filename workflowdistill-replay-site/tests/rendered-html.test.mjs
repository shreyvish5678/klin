import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the validation replay", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(
    html,
    /<title>WorkflowDistill — Discord → Bonsai Validation Replay<\/title>/i,
  );
  assert.match(html, /Research event stream/);
  assert.match(html, /Measured evidence/);
  assert.match(html, /Next-candidate target/);
  assert.match(html, /Bonsai did not beat the hosted control/);
  assert.match(html, /121 EVENTS SEALED/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});

test("keeps measured and target claims visibly distinct", async () => {
  const response = await render();
  const html = await response.text();

  assert.match(html, /GPT-5\.6-sol/);
  assert.match(html, /Bonsai 27B Q1/);
  assert.match(html, /Bonsai \+ p42/);
  assert.match(html, /Best measured/);
  assert.match(html, /Did not qualify/);
  assert.match(html, /Rejected/);
  assert.match(html, /Derived from measured failure signatures; not yet evaluated/);
  assert.match(html, /production stayed untouched/);
});
