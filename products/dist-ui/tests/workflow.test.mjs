import test from "node:test";
import assert from "node:assert/strict";
import { createWorkflow } from "../server/workflow.mjs";

test("workflow emits a complete ordered event contract", () => {
  const events = createWorkflow({
    runId: "test-run",
    agentId: "discord-agent",
    message: "Replace the hosted model",
  });

  assert.equal(events[0].event_type, "RUN_CREATED");
  assert.equal(events.at(-1).event_type, "RUN_COMPLETED");
  assert.equal(events.at(-1).status, "completed");
  assert.equal(events.at(-1).progress, 100);
  assert.deepEqual(
    events.map((event) => event.sequence),
    Array.from({ length: events.length }, (_, index) => index + 1),
  );
});

test("workflow keeps user input bounded and on the selected agent", () => {
  const events = createWorkflow({
    runId: "bounded-run",
    agentId: "prompt-builder",
    message: `  ${"inspect ".repeat(100)}  `,
  });

  assert.equal(events[0].agent_id, "prompt-builder");
  assert.ok(events[0].detail.length <= 240);
  assert.match(events[2].summary, /prompt-builder/);
});

test("workflow covers all visible regression cases", () => {
  const events = createWorkflow({
    runId: "case-run",
    agentId: "discord-agent",
    message: "Audit the workflow",
  });
  const completedCases = events.flatMap((event) => (event.test ? [event.test.id] : []));

  assert.deepEqual(completedCases, [
    "ambiguous-recipient",
    "confirmed-send",
    "private-search",
    "duplicate-resistance",
    "one-cursor",
  ]);
});

test("replay exposes sealed evidence provenance and honest verdict", () => {
  const events = createWorkflow({
    runId: "evidence-run",
    agentId: "discord-agent",
    message: "Audit the workflow",
  });

  assert.ok(events.every((event) => event.evidence_mode === "sealed_run_replay"));
  assert.ok(events.every((event) => event.source_run_id.endsWith("322363")));
  assert.match(events.at(-1).summary, /NOT YET/);
  assert.equal(events.at(-1).method, "Final handoff");
  assert.deepEqual(
    [
      events.at(-1).metrics.hosted_passed,
      events.at(-1).metrics.bonsai_passed,
      events.at(-1).metrics.p42_passed,
    ],
    [4, 1, 0],
  );
});

test("parallel branches fan out, terminate, and join before evaluation", () => {
  const events = createWorkflow({
    runId: "parallel-run",
    agentId: "discord-agent",
    message: "Compare model-boundary methods",
  });
  const branchIds = ["hosted", "bonsai", "p42"];
  const starts = branchIds.map((branchId) =>
    events.find((event) => event.branch_id === branchId && event.branch_status === "running"),
  );
  const terminals = branchIds.map((branchId) =>
    events.findLast(
      (event) =>
        event.branch_id === branchId &&
        ["completed", "rejected"].includes(event.branch_status),
    ),
  );
  const evaluationStart = events.find((event) => event.event_type === "EVALUATION_STARTED");

  assert.ok(starts.every(Boolean));
  assert.ok(terminals.every(Boolean));
  assert.ok(Math.max(...starts.map((event) => event.sequence)) < Math.min(...terminals.map((event) => event.sequence)));
  assert.ok(Math.max(...terminals.map((event) => event.sequence)) < evaluationStart.sequence);
  assert.deepEqual(
    terminals.map((event) => event.branch_status),
    ["rejected", "rejected", "rejected"],
  );
  assert.deepEqual(
    terminals.map((event) => event.branch_tests),
    [
      { passed: 4, total: 9 },
      { passed: 1, total: 9 },
      { passed: 0, total: 9 },
    ],
  );
});
