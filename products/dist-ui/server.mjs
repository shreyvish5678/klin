import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import express from "express";
import {
  agents,
  createWorkflow,
  latestReport,
  outerPhases,
  testCases,
} from "./server/workflow.mjs";

const execFileAsync = promisify(execFile);
const app = express();
const port = Number(process.env.PORT) || 5173;
const isProduction = process.env.NODE_ENV === "production";
const runs = new Map();
const root = path.dirname(fileURLToPath(import.meta.url));

app.use(express.json({ limit: "32kb" }));

app.get("/api/health", (_request, response) => {
  response.json({ ok: true, service: "work-distill-orchestrator" });
});

app.get("/api/runtime", async (_request, response) => {
  try {
    const { stdout } = await execFileAsync("codex", ["--version"], {
      timeout: 2500,
      env: process.env,
    });
    response.json({
      available: true,
      label: stdout.trim() || "codex cli",
    });
  } catch {
    response.json({ available: false, label: "codex cli unavailable" });
  }
});

app.get("/api/workspace", (_request, response) => {
  response.json({
    workspace: "navilan / agents",
    orchestratorMode: "sealed-run-replay",
    latestReport,
    agents,
    outerPhases,
    testCases,
  });
});

app.post("/api/runs", (request, response) => {
  const runId = randomUUID().slice(0, 8);
  const message = String(request.body?.message || "").trim();
  const agentId = String(request.body?.agentId || agents[0].id);
  const events = createWorkflow({ runId, message, agentId });

  runs.set(runId, {
    id: runId,
    createdAt: Date.now(),
    cursor: 0,
    events,
  });

  response.status(201).json({
    runId,
    streamUrl: `/api/runs/${runId}/events`,
    evidenceMode: "sealed_run_replay",
    replaySpeed: 10,
  });
});

app.get("/api/runs/:runId/events", (request, response) => {
  const run = runs.get(request.params.runId);

  if (!run) {
    response.status(404).json({ error: "Run not found" });
    return;
  }

  response.setHeader("Content-Type", "text/event-stream");
  response.setHeader("Cache-Control", "no-cache, no-transform");
  response.setHeader("Connection", "keep-alive");
  response.flushHeaders();

  const sendNext = () => {
    const event = run.events[run.cursor];
    if (!event) {
      response.write("event: end\ndata: {}\n\n");
      response.end();
      runs.delete(run.id);
      return false;
    }

    response.write(`id: ${event.sequence}\n`);
    response.write(`event: workflow\n`);
    response.write(`data: ${JSON.stringify(event)}\n\n`);
    run.cursor += 1;
    return true;
  };

  sendNext();
  const timer = setInterval(() => {
    if (!sendNext()) clearInterval(timer);
  }, 180);

  request.on("close", () => {
    clearInterval(timer);
    runs.delete(run.id);
  });
});

if (isProduction) {
  app.use(express.static(path.join(root, "dist")));
  app.get("/{*splat}", (_request, response) => {
    response.sendFile(path.join(root, "dist", "index.html"));
  });
} else {
  const { createServer } = await import("vite");
  const vite = await createServer({
    server: { middlewareMode: true },
    appType: "spa",
  });
  app.use(vite.middlewares);
}

app.listen(port, "127.0.0.1", () => {
  console.log(`Work Distill ready at http://127.0.0.1:${port}`);
});
