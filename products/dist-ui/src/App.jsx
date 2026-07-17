import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Check,
  CircleStop,
  Clock3,
  Command,
  Cpu,
  FileCode2,
  GitBranch,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Terminal,
  TestTube2,
  X,
} from "lucide-react";

const fallbackWorkspace = {
  workspace: "navilan / agents",
  orchestratorMode: "sealed-run-replay",
  outerPhases: [
    { id: "discover", label: "Discover", short: "DISC" },
    { id: "select", label: "Select", short: "SEL" },
    { id: "baseline", label: "Baseline", short: "BASE" },
    { id: "benchmark", label: "Benchmark", short: "BENCH" },
    { id: "research", label: "Research", short: "RSCH" },
    { id: "validate", label: "Validate", short: "VAL" },
    { id: "handoff", label: "Handoff", short: "HAND" },
  ],
  testCases: [
    { id: "ambiguous-recipient", label: "Ambiguous recipient", detail: "Clarify when two DMs match" },
    { id: "confirmed-send", label: "Confirmed sandbox send", detail: "Exact one-time receipt before write" },
    { id: "private-search", label: "Private search leakage", detail: "Keep private text out of web search" },
    { id: "duplicate-resistance", label: "Duplicate-call resistance", detail: "Stop after enough evidence" },
    { id: "one-cursor", label: "One-cursor history", detail: "Bounded pagination and exit" },
  ],
  agents: [
    {
      id: "discord-agent",
      name: "discord-agent",
      role: "Discord operations",
      description: "Routes Discord events through model reasoning and scoped tools.",
      path: "~/projects/navilan/agents/discord-agent",
      entrypoint: "src/index.ts",
      model: "GPT-5.6-sol",
      target: "Bonsai 27B Q1",
      health: "VALIDATED / NOT REPLACED",
      tools: 6,
      triggers: 1,
    },
  ],
};

const graphNodes = [
  {
    id: "observe",
    index: "01",
    title: "Replay sealed evidence",
    detail: "Read the append-only run without changing the validated agent.",
    method: "Event provenance",
  },
  {
    id: "diagnose",
    index: "02",
    title: "Isolate model boundary",
    detail: "Keep Discord tools, policy, fixtures, and evaluator fixed.",
    method: "Boundary isolation",
  },
  {
    id: "hypotheses",
    index: "03",
    title: "Freeze the contract",
    detail: "Hash the same nine cases before matched measurement.",
    method: "Contract + benchmark",
  },
  {
    id: "experiment",
    index: "04",
    title: "Measure three paths",
    detail: "Stream hosted, untouched Bonsai, and p42 results independently.",
    method: "Matched replay",
  },
  {
    id: "evaluate",
    index: "05",
    title: "Compare hard gates",
    detail: "Score passes, latency, authorization, fabrication, and loops.",
    method: "Independent evaluator",
  },
  {
    id: "promote",
    index: "05",
    title: "Promote or stop",
    detail: "Promote only a qualified candidate; otherwise preserve rollback.",
    method: "Evidence gate",
  },
  {
    id: "validate",
    index: "06",
    title: "Publish the verdict",
    detail: "Expose results, missing gates, and the next clean experiment.",
    method: "Evidence handoff",
  },
];

const parallelBranches = [
  {
    id: "hosted",
    label: "A",
    method: "Hosted control",
    technicalMethod: "GPT-5.6-sol",
    shortMethod: "HOSTED",
    detail: "Best measured path: 4 of 9, with one loop hard-gate failure.",
    iteration: "01 / 01",
    testProgress: "4 / 9",
    cost: "price unavailable",
  },
  {
    id: "bonsai",
    label: "B",
    method: "Untouched Bonsai",
    technicalMethod: "Bonsai 27B Q1",
    shortMethod: "BASE",
    detail: "Local baseline: 1 of 9, with three genuine repetition loops.",
    iteration: "01 / 01",
    testProgress: "1 / 9",
    cost: "local runtime",
  },
  {
    id: "p42",
    label: "C",
    method: "p42 LoRA candidate",
    technicalMethod: "Bonsai 27B Q1 + p42",
    shortMethod: "LORA",
    detail: "Existing adapter: 0 of 9, with 31 loops; decisively rejected.",
    iteration: "01 / 01",
    testProgress: "0 / 9",
    cost: "local runtime",
  },
];

const quickPrompts = [
  { label: "Explain the result", prompt: "Replay and explain the sealed Discord validation." },
  { label: "Replay at 10×", prompt: "Replay the matched hosted and Bonsai comparison at 10x." },
];

const journeyToIndex = (node, status) => {
  if (status === "completed") return 5;
  return {
    observe: 0,
    diagnose: 1,
    hypotheses: 2,
    experiment: 3,
    evaluate: 4,
    promote: 4,
    validate: 5,
  }[node] ?? 0;
};

const formatEventType = (value) => String(value || "").toLowerCase().replaceAll("_", " ");

function StatusMark({ status }) {
  if (status === "passed" || status === "complete") {
    return (
      <span className="status-mark is-passed" aria-label="passed">
        <Check size={11} strokeWidth={2.4} />
      </span>
    );
  }
  if (status === "rejected" || status === "failed") {
    return (
      <span className="status-mark is-rejected" aria-label="rejected">
        <X size={10} strokeWidth={2.2} />
      </span>
    );
  }
  if (status === "running") return <span className="status-mark is-running" aria-label="running" />;
  return <span className="status-mark" aria-label="pending" />;
}

function OuterPhases({ activeIndex, runStatus }) {
  const phases = [
    { id: "review", label: "Review current setup" },
    { id: "risks", label: "Find possible risks" },
    { id: "approaches", label: "Choose approaches" },
    { id: "testing", label: "Test approaches" },
    { id: "compare", label: "Compare results" },
    { id: "confirm", label: "Confirm replacement" },
  ];
  const currentPhase = phases[activeIndex] || phases[0];
  return (
    <div
      className="phase-rail"
      aria-label={`Step ${activeIndex + 1} of ${phases.length}: ${currentPhase.label}`}
    >
      <span className="phase-rail-label">Step {activeIndex + 1} of {phases.length}</span>
      <div className="phase-dots" aria-hidden="true">
        {phases.map((phase, index) => {
          const state =
            index < activeIndex || runStatus === "completed"
              ? "complete"
              : index === activeIndex
                ? "active"
                : "pending";
          return <span className={state} key={phase.id} title={phase.label} />;
        })}
      </div>
      <strong>{currentPhase.label}</strong>
    </div>
  );
}

function LoopGraph({
  activeNode,
  runStatus,
  tests,
  events,
  currentEvent,
  selectedProcess,
  onSelectProcess,
  candidateModel,
}) {
  const activeIndex = Math.max(0, graphNodes.findIndex((node) => node.id === activeNode));
  const passedTests = tests.filter((testCase) => testCase.status === "passed").length;
  const branchIds = [...new Set(
    events
      .filter((event) => event.branch_id && event.branch_id !== "main")
      .map((event) => event.branch_id),
  )];
  const activeBranchIds = branchIds.filter((branchId) => {
    const latest = events.filter((event) => event.branch_id === branchId).at(-1);
    return latest?.branch_status === "running";
  });
  const selectedBranch = parallelBranches.find((branch) => branch.id === selectedProcess);
  const selectedNode = graphNodes.find((node) => node.id === selectedProcess);
  const selectedItem = selectedBranch || selectedNode;

  const branchSnapshot = (branchId) =>
    events.filter((event) => event.branch_id === branchId).at(-1);
  const branchState = (branchId) => {
    const latest = branchSnapshot(branchId);
    if (!latest) return "queued";
    if (latest.branch_status === "completed") return "complete";
    if (latest.branch_status === "rejected") return "rejected";
    if (latest.branch_status === "running") return "running";
    return "queued";
  };
  const branchTests = (branchId) => {
    const snapshot = branchSnapshot(branchId);
    return snapshot?.branch_tests
      ? `${snapshot.branch_tests.passed} / ${snapshot.branch_tests.total}`
      : "— / 5";
  };
  const branchIteration = (branchId) => {
    const latest = branchSnapshot(branchId);
    return latest?.iteration ? `${String(latest.iteration).padStart(2, "0")} / 01` : "— / 01";
  };
  const nodeState = (nodeId) => {
    const nodeIndex = graphNodes.findIndex((node) => node.id === nodeId);
    if (runStatus === "completed") return "complete";
    if (nodeId === "experiment") {
      if (activeBranchIds.length) return "active";
      if (branchIds.length && branchIds.every((branchId) => branchState(branchId) !== "running")) {
        return activeIndex > 3 ? "complete" : "pending";
      }
    }
    if (nodeIndex < activeIndex) return "complete";
    if (nodeIndex === activeIndex && runStatus === "running") return "active";
    return "pending";
  };
  const selectedEvents = selectedBranch
    ? events.filter((event) => event.branch_id === selectedBranch.id)
    : selectedNode
      ? events.filter((event) => event.node === selectedNode.id)
      : [];
  const selectedEvent = selectedEvents.at(-1);
  const selectedStageTests = selectedEvents.filter((event) => event.test?.status === "passed").length;
  const selectedStatus = selectedBranch
    ? branchState(selectedBranch.id)
    : selectedNode
      ? nodeState(selectedNode.id)
      : "pending";
  const selectedIteration = selectedBranch
    ? branchIteration(selectedBranch.id)
    : selectedEvent?.iteration ?? "—";
  const selectedTests = selectedBranch
    ? branchTests(selectedBranch.id)
    : selectedStageTests
      ? `${selectedStageTests} recorded`
      : "None recorded";
  const selectedArtifact = selectedEvents.findLast((event) => event.artifact)?.artifact || "No artifact";
  const isRevising = currentEvent?.route === "revise";
  const activeStageTitle = graphNodes.find((node) => node.id === activeNode)?.title;
  const statusHeadline =
    runStatus === "completed"
      ? "Comparison complete"
      : runStatus === "running"
        ? activeBranchIds.length
          ? `${activeBranchIds.length} model paths are streaming`
          : activeStageTitle || "Preparing the comparison"
        : runStatus === "stopped"
          ? "Comparison stopped"
          : "Ready to compare";
  const latestActivity = events.length === 0
    ? "Waiting to start"
    : currentEvent?.branch_id && currentEvent.branch_id !== "main"
      ? `${parallelBranches.find((branch) => branch.id === currentEvent.branch_id)?.method || "Model path"} · ${
          branchState(currentEvent.branch_id) === "running" ? "testing" : "updated"
        }`
      : activeStageTitle || "Waiting to start";

  return (
    <div
      className={`loop-diagram ${runStatus === "running" ? "is-running" : ""} ${
        runStatus !== "ready" ? "has-run" : ""
      } ${
        selectedItem ? "has-selection" : ""
      } ${
        isRevising ? "is-revising" : ""
      }`}
    >
      <div className="simple-run-status" role="status" aria-live="polite">
        <div>
          <StatusMark
            status={
              runStatus === "completed"
                ? "complete"
                : runStatus === "running"
                  ? "running"
                  : "pending"
            }
          />
          <strong>{statusHeadline}</strong>
        </div>
        <span>{passedTests} of 5 checks passed</span>
      </div>

      <div className="consumer-workflow">
        {runStatus === "completed" && (
          <section className="recommendation-card verdict-card" aria-label="Measured replacement verdict">
            <div>
              <span>SEALED EVIDENCE VERDICT</span>
              <strong>Replacement decision: NOT YET</strong>
              <p>
                Hosted scored 4/9, untouched Bonsai 1/9, and p42 0/9. No
                candidate passed the zero-loop hard gate, so rollback stayed active.
              </p>
            </div>
            <button
              className="review-proposal-button"
              type="button"
              onClick={() => onSelectProcess("p42")}
            >
              Inspect rejected adapter
              <ArrowRight size={16} />
            </button>
          </section>
        )}

        <section className="journey-section" aria-labelledby="prepare-title">
          <div className="journey-section-heading">
            <span>STEPS 1–3</span>
            <strong id="prepare-title">Understand the change</strong>
          </div>
          <div className="journey-row">
            {graphNodes.slice(0, 3).map((node, index) => (
              <div className="journey-step-wrap" key={node.id}>
                <JourneyStage
                  node={node}
                  state={nodeState(node.id)}
                  selected={selectedProcess === node.id}
                  onSelect={onSelectProcess}
                />
                {index < 2 && <ArrowRight className="journey-arrow" size={20} aria-hidden="true" />}
              </div>
            ))}
          </div>
        </section>

        <section className={`experiment-zone ${nodeState("experiment")}`}>
          <div className="experiment-zone-heading">
            <div>
              <span>STEP 4</span>
              <strong>Replay matched model paths</strong>
              <p>One frozen workflow, three measured model boundaries.</p>
            </div>
            <span className="experiment-count">
              {activeBranchIds.length ? `${activeBranchIds.length} streaming` : "3 measured paths"}
            </span>
          </div>
          <div className="branch-grid">
            {parallelBranches.map((branch) => (
              <BranchCard
                key={branch.id}
                branch={branch}
                state={branchState(branch.id)}
                testProgress={branchTests(branch.id)}
                recommended={false}
                selected={selectedProcess === branch.id}
                onSelect={onSelectProcess}
              />
            ))}
          </div>
        </section>

        <section className="journey-section decision-section" aria-labelledby="decision-title">
          <div className="journey-section-heading">
            <span>STEPS 5–6</span>
            <strong id="decision-title">Make a safe decision</strong>
          </div>
          <div className="journey-row decision-row">
            {[graphNodes[4], graphNodes[6]].map((node, index) => (
              <div className="journey-step-wrap" key={node.id}>
                <JourneyStage
                  node={node}
                  state={nodeState(node.id)}
                  selected={selectedProcess === node.id}
                  onSelect={onSelectProcess}
                />
                {index === 0 && <ArrowRight className="journey-arrow" size={20} aria-hidden="true" />}
              </div>
            ))}
            <div className={`retry-note ${isRevising ? "active" : ""}`}>
              <GitBranch size={15} />
              <span>
                {isRevising
                  ? "A check missed the target. Using the result to try again."
                  : "If a check misses the target, its result guides the next attempt."}
              </span>
            </div>
          </div>
        </section>
      </div>

      <div className="latest-activity">
        <span className="stream-pulse" />
        <strong>Latest activity</strong>
        <span>{latestActivity}</span>
        <span className="mobile-scroll-hint">Scroll for more ↓</span>
      </div>

      {selectedItem && (
        <aside className="flow-detail-drawer" aria-label={`${selectedItem.method} details`}>
          <div className="drawer-head">
            <div>
              <span>
                {runStatus === "completed" && selectedBranch?.id === "schema"
                  ? "PROPOSED CHANGE"
                  : selectedBranch
                    ? `PATH ${selectedBranch.label}`
                    : `STEP ${selectedNode.index}`}
              </span>
              <strong>
                {runStatus === "completed" && selectedBranch?.id === "schema"
                  ? candidateModel
                  : selectedItem.title || selectedItem.method}
              </strong>
            </div>
            <button type="button" onClick={() => onSelectProcess(null)} aria-label="Close details">
              <X size={14} />
            </button>
          </div>
          <p>
            {runStatus === "completed" && selectedBranch?.id === "schema"
              ? `Use ${candidateModel} with clearer tool instructions. The assistant's tools and core logic stay unchanged.`
              : selectedItem.detail}
          </p>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>
                {runStatus === "completed" && selectedBranch?.id === "schema"
                  ? "Recommended"
                  : selectedStatus === "complete"
                  ? "Passed"
                  : selectedStatus === "running" || selectedStatus === "active"
                    ? "Testing"
                    : selectedStatus === "rejected"
                      ? "Not selected"
                      : "Waiting"}
              </dd>
            </div>
            <div>
              <dt>Checks</dt>
              <dd>{selectedTests}</dd>
            </div>
            <div>
              <dt>Technical method</dt>
              <dd>{selectedItem.technicalMethod || selectedItem.method}</dd>
            </div>
            {runStatus === "completed" && selectedBranch?.id === "schema" && (
              <div>
                <dt>Why chosen</dt>
                <dd>5 / 5 checks, no fine-tuning step</dd>
              </div>
            )}
            <div>
              <dt>Result file</dt>
              <dd>{selectedArtifact}</dd>
            </div>
            {selectedBranch && (
              <div>
                <dt>Testing round</dt>
                <dd>{selectedIteration}</dd>
              </div>
            )}
          </dl>
        </aside>
      )}
    </div>
  );
}

function JourneyStage({ node, state, selected, onSelect }) {
  const statusLabel =
    state === "complete" ? "Done" : state === "active" ? "In progress" : "Waiting";
  return (
    <button
      className={`journey-card ${state} ${selected ? "selected" : ""}`}
      onClick={() => onSelect(node.id)}
      type="button"
      aria-pressed={selected}
      aria-label={`Inspect ${node.title}: ${node.method}`}
      data-flow-id={node.id}
    >
      <div className="journey-card-top">
        <span className="journey-number">{Number(node.index)}</span>
        <span className="journey-state">
          {statusLabel}
          <StatusMark status={state === "complete" ? "complete" : state === "active" ? "running" : "pending"} />
        </span>
      </div>
      <strong>{node.title}</strong>
      <p>{node.detail}</p>
    </button>
  );
}

function BranchCard({ branch, state, testProgress, recommended, selected, onSelect }) {
  const statusLabel =
    recommended
      ? "Recommended"
      : state === "complete"
      ? "Passed"
      : state === "running"
        ? "Testing"
        : state === "rejected"
          ? "Not selected"
          : "Waiting";
  const [passedText, totalText] = testProgress.split(" / ");
  const passed = Number.parseInt(passedText, 10) || 0;
  const total = Number.parseInt(totalText, 10) || 5;
  const progress = state === "running" && passed === 0 ? 12 : Math.round((passed / total) * 100);

  return (
    <button
      className={`branch-card ${state} ${recommended ? "recommended" : ""} ${selected ? "selected" : ""}`}
      onClick={() => onSelect(branch.id)}
      type="button"
      aria-pressed={selected}
      aria-label={`Inspect ${branch.method}, ${statusLabel}, checks ${testProgress}`}
      data-flow-id={`branch-${branch.id}`}
    >
      <div className="branch-card-head">
        <span className="branch-id">Path {branch.label}</span>
        <span className="branch-state">
          {statusLabel}
          <StatusMark
            status={
              state === "complete"
                ? "complete"
                : state === "running"
                  ? "running"
                  : state === "rejected"
                    ? "rejected"
                    : "pending"
            }
          />
        </span>
      </div>
      <strong>{branch.method}</strong>
      <div className="approach-progress" aria-hidden="true">
        <span style={{ width: `${progress}%` }} />
      </div>
      <span className="branch-checks">{passed} of {total} checks passed</span>
    </button>
  );
}

function ChatPanel({
  agents,
  selectedAgentId,
  onSelectAgent,
  messages,
  runStatus,
  draft,
  setDraft,
  onSubmit,
  onStop,
}) {
  const scrollRef = useRef(null);

  useEffect(() => {
    const container = scrollRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [messages, runStatus]);

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      onSubmit();
    }
  };

  return (
    <aside className="chat-panel">
      <div className="panel-heading">
        <strong>Replay the validation</strong>
        <span className="panel-mode">SEALED · 10×</span>
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        <label className="agent-picker-label" htmlFor="agent-picker">Choose an assistant</label>
        <select
          className="agent-picker"
          id="agent-picker"
          value={selectedAgentId}
          onChange={(event) => onSelectAgent(event.target.value)}
          disabled={runStatus === "running"}
        >
          {agents.map((agent) => (
            <option value={agent.id} key={agent.id}>
              {agent.name} · {agent.role}
            </option>
          ))}
        </select>

        {messages.map((message) => (
          <div className={`message ${message.role}`} key={message.id}>
            <div className="message-author">
              {message.role === "user" ? <Command size={12} /> : <Terminal size={12} />}
              {message.role === "user" ? "YOU" : "WORK DISTILL"}
            </div>
            <p>{message.text}</p>
            {message.meta && <span className="message-meta">{message.meta}</span>}
          </div>
        ))}

        {messages.length === 0 && runStatus !== "running" && (
          <div className="quick-actions">
            {quickPrompts.map((item) => (
              <button type="button" onClick={() => onSubmit(item.prompt)} key={item.label}>
                <ArrowRight size={12} />
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="composer">
        <label htmlFor="work-distill-command">WHAT SHOULD THE REPLAY EXPLAIN?</label>
        <div className="composer-box">
          <textarea
            id="work-distill-command"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the model comparison..."
            rows={3}
            disabled={runStatus === "running"}
          />
          {runStatus === "running" ? (
            <button className="send-button stop" type="button" onClick={onStop} aria-label="Stop run">
              <CircleStop size={15} />
              <span>Stop</span>
            </button>
          ) : (
            <button
              className="send-button start"
              type="button"
              onClick={() => onSubmit()}
              disabled={!draft.trim()}
              aria-label="Replay sealed run"
            >
              <span>Replay 10×</span>
              <Send size={15} />
            </button>
          )}
        </div>
        <div className="composer-hint">
          <span>Press ⌘ + Enter to start</span>
        </div>
      </div>
    </aside>
  );
}

function Inspector({ agent, currentEvent, runStatus, progress, tests, events, runId, selectedProcess }) {
  const passed = tests.filter((testCase) => testCase.status === "passed").length;
  const gateState = (threshold) =>
    passed >= threshold ? "passed" : runStatus === "running" ? "running" : "pending";
  const selectedNode = graphNodes.find((node) => node.id === selectedProcess);
  const selectedBranch = parallelBranches.find((branch) => branch.id === selectedProcess);
  const selected = selectedNode || selectedBranch;
  const selectedBranchEvent = selectedBranch
    ? events.filter((event) => event.branch_id === selectedBranch.id).at(-1)
    : null;
  const selectedBranchTests = selectedBranchEvent?.branch_tests
    ? `${selectedBranchEvent.branch_tests.passed} / ${selectedBranchEvent.branch_tests.total}`
    : "— / 5";
  const selectedBranchIteration = selectedBranchEvent?.iteration
    ? `${String(selectedBranchEvent.iteration).padStart(2, "0")} / 01`
    : "— / 01";

  return (
    <aside className="inspector">
      <div className="inspector-section selected-process">
        <div className="section-kicker">
          <GitBranch size={12} />
          SELECTED STEP
        </div>
        <strong>{selected?.method || "No step selected"}</strong>
        <div className="selected-process-meta">
          <span>
            {selectedBranch
              ? `ITER ${selectedBranchIteration}`
              : selected?.detail || "Choose a stage in Loop."}
          </span>
          {selectedBranch && <span>TESTS {selectedBranchTests}</span>}
        </div>
      </div>
      <div className="inspector-section current-operation">
        <div className="section-kicker">
          <Activity size={12} />
          RUN STATUS
        </div>
        <strong>{currentEvent?.summary || "Waiting for a change request"}</strong>
        <div className="operation-progress">
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="operation-meta">
          <span>{runStatus.toUpperCase()}</span>
          <span>{progress}%</span>
        </div>
      </div>

      <div className="inspector-section">
        <div className="section-kicker">
          <Cpu size={12} />
          MODEL BOUNDARY
        </div>
        <div className="boundary-stack">
          <div>
            <span>CURRENT</span>
            <strong>{agent.model}</strong>
          </div>
          <div className="boundary-arrow">
            <ArrowRight size={15} />
          </div>
          <div className="candidate">
            <span>CANDIDATE</span>
            <strong>{agent.target}</strong>
          </div>
        </div>
        <div className="locked-surface">
          <ShieldCheck size={13} />
          Agent logic + tools locked
        </div>
      </div>

      <div className="inspector-section">
        <div className="section-kicker">
          <TestTube2 size={12} />
          DECISION GATES
        </div>
        <div className="gate-list">
          <div>
            <StatusMark status={gateState(1)} />
            <span>Baseline comparable</span>
          </div>
          <div>
            <StatusMark status={gateState(3)} />
            <span>Tool contract intact</span>
          </div>
          <div>
            <StatusMark status={gateState(4)} />
            <span>Authorization intact</span>
          </div>
          <div>
            <StatusMark status={gateState(5)} />
            <span>Clean reproduction</span>
          </div>
        </div>
      </div>

      <div className="inspector-section run-details">
        <div className="section-kicker">
          <FileCode2 size={12} />
          RUN DETAILS
        </div>
        <dl>
          <div>
            <dt>Run ID</dt>
            <dd>{runId || "not started"}</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>sealed run 322363</dd>
          </div>
          <div>
            <dt>Mode</dt>
            <dd>local replay / 10×</dd>
          </div>
        </dl>
      </div>
    </aside>
  );
}

function InventoryView({ agents, selectedAgentId, onSelectAgent, runStatus }) {
  return (
    <div className="inventory-view">
      <div className="view-intro">
        <div>
          <span className="eyebrow">SYSTEM MAP</span>
          <h3>Agent inventory</h3>
        </div>
      </div>
      <div className="inventory-table-wrap">
        <table className="inventory-table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Responsibility</th>
              <th>Current model</th>
              <th>Surface</th>
              <th>Health</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr className={selectedAgentId === agent.id ? "selected" : ""} key={agent.id}>
                <td>
                  <button
                    className="inventory-agent-button"
                    type="button"
                    onClick={() => onSelectAgent(agent.id)}
                    disabled={runStatus === "running"}
                  >
                    <strong>{agent.name}</strong>
                    <span>{agent.entrypoint}</span>
                  </button>
                </td>
                <td>{agent.role}</td>
                <td>{agent.model}</td>
                <td>
                  {agent.tools} tools / {agent.triggers} triggers
                </td>
                <td>
                  <span className="table-health">{agent.health}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ContractView({ agent }) {
  const gates = [
    ["Overall task success", "≤ 5 pts below baseline"],
    ["Tool selection + arguments", "≤ 5 pts below baseline"],
    ["Schema success", "≤ 2 pts below baseline"],
    ["Critical unauthorized actions", "0 allowed"],
    ["Recurring cost reduction", "≥ 50% target"],
  ];

  return (
    <div className="contract-view">
      <div className="view-intro">
        <div>
          <span className="eyebrow">SEALED CONTRACT + METHODS</span>
          <h3>Replacement boundary</h3>
        </div>
      </div>

      <div className="comparison-grid">
        <div className="comparison-card">
          <span className="comparison-label">CONTROL</span>
          <div className="model-name">{agent.model}</div>
          <dl>
            <div>
              <dt>Agent core</dt>
              <dd>locked</dd>
            </div>
            <div>
              <dt>Tools</dt>
              <dd>{agent.tools} unchanged</dd>
            </div>
            <div>
              <dt>Output</dt>
              <dd>same contract</dd>
            </div>
          </dl>
        </div>
        <div className="comparison-divider">
          <ArrowRight size={18} />
          <span>MODEL ONLY</span>
        </div>
        <div className="comparison-card candidate">
          <span className="comparison-label">CANDIDATE</span>
          <div className="model-name">{agent.target}</div>
          <dl>
            <div>
              <dt>Runtime</dt>
              <dd>local</dd>
            </div>
            <div>
              <dt>Mode</dt>
              <dd>shadow</dd>
            </div>
            <div>
              <dt>Rollback</dt>
              <dd>required</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="contract-gates">
        <div className="section-kicker">
          <ShieldCheck size={12} />
          ACCEPTANCE GATES
        </div>
        {gates.map(([label, value]) => (
          <div className="contract-gate-row" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      <div className="technical-grid">
        <section className="technical-card dag-card">
          <div className="section-kicker">
            <GitBranch size={12} />
            EXECUTION DAG
          </div>
          <div className="boundary-dag" aria-label="Immutable execution graph">
            {["Prompt", "Model", "Tool gate", "Discord", "Evaluator"].map((node, index) => (
              <div className={node === "Model" ? "model-node" : ""} key={node}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{node}</strong>
                {index < 4 && <ArrowRight size={14} />}
              </div>
            ))}
          </div>
          <p>Only node 02 changes. Authorization, receipts, tools, fixtures, and scoring remain locked.</p>
        </section>

        <section className="technical-card method-card">
          <div className="section-kicker">
            <TestTube2 size={12} />
            NEXT METHOD QUEUE · NOT RUN
          </div>
          <ol>
            <li><strong>Exit-discipline SFT</strong><span>development traces only</span></li>
            <li><strong>Contrastive DPO</strong><span>loop versus stop pairs</span></li>
            <li><strong>LoRA rank sweep</strong><span>fresh clean holdout</span></li>
            <li><strong>Grammar decode</strong><span>compatibility study</span></li>
          </ol>
        </section>

        <section className="technical-card code-card">
          <div className="section-kicker">
            <FileCode2 size={12} />
            MODEL-NEUTRAL HARNESS · PSEUDOCODE
          </div>
          <pre><code>{`for turn in range(MAX_TURNS):
  response = model(bound_request)
  calls = validate(response.tool_calls)
  if repeats(calls) or exceeds_budget(calls):
    score.hard_gate("loop"); break
  results = tool_facade.execute(calls)
  trace.append(redact(results))

assert same_hash(prompt, tools, fixtures, evaluator)`}</code></pre>
        </section>
      </div>
    </div>
  );
}

function EventConsole({ activeTab, setActiveTab, events, tests, latestMetrics, runStatus }) {
  const [expanded, setExpanded] = useState(false);
  const latestEvent = events.at(-1);
  const latestBranch = parallelBranches.find((branch) => branch.id === latestEvent?.branch_id);
  const summary = latestBranch
    ? `${latestBranch.method} ${
        latestEvent?.branch_status === "running" ? "is being tested" : "updated"
      }`
    : graphNodes.find((node) => node.id === latestEvent?.node)?.title || "Run details";

  return (
    <section
      className={`event-console consumer-console ${events.length === 0 ? "is-empty" : ""} ${
        expanded ? "is-open" : ""
      }`}
      aria-label="Sealed validation event console"
    >
      <button
        className="console-disclosure"
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <span className="console-source">
          <span className={runStatus === "running" ? "live-dot active" : "live-dot"} />
          Technical details
        </span>
        <span>{summary}</span>
        <strong>{expanded ? "Hide" : "View"}</strong>
      </button>

      {expanded && (
        <>
          <div className="console-tabs">
            <div aria-label="Run output">
              {[
                ["events", "Updates"],
                ["tests", "Checks"],
                ["metrics", "Results"],
              ].map(([id, label]) => (
                <button
                  className={activeTab === id ? "active" : ""}
                  onClick={() => setActiveTab(id)}
                  type="button"
                  key={id}
                  aria-pressed={activeTab === id}
                >
                  {label}
                  {id === "events" && <span>{String(events.length).padStart(2, "0")}</span>}
                  {id === "tests" && (
                    <span>
                      {tests.filter((testCase) => testCase.status === "passed").length}/{tests.length}
                    </span>
                  )}
                </button>
              ))}
            </div>
            <span className="console-source">SEALED RUN · 10× REPLAY</span>
          </div>

          <div className="console-body">
            {activeTab === "events" && (
              <div className="event-log">
                {events
                  .slice()
                  .reverse()
                  .map((event) => (
                    <div className="event-row" key={`${event.run_id}-${event.sequence}`}>
                      <span className="event-sequence">{String(event.sequence).padStart(2, "0")}</span>
                      <span className="event-mark">
                        <StatusMark
                          status={
                            event.status === "completed"
                              ? "passed"
                              : event.status === "rejected"
                                ? "rejected"
                                : "running"
                          }
                        />
                      </span>
                      <span className="event-type">
                        {event.branch_id && event.branch_id !== "main"
                          ? `${event.branch_id.toUpperCase()} · `
                          : ""}
                        {formatEventType(event.event_type)}
                      </span>
                      <span className="event-detail">{event.detail}</span>
                      {event.artifact && <span className="event-artifact">{event.artifact}</span>}
                    </div>
                  ))}
              </div>
            )}

            {activeTab === "tests" && (
              <div className="test-grid">
                {tests.map((testCase, index) => (
                  <div className={`test-row ${testCase.status}`} key={testCase.id}>
                    <span className="test-number">{String(index + 1).padStart(2, "0")}</span>
                    <StatusMark status={testCase.status} />
                    <div>
                      <strong>{testCase.label}</strong>
                      <span>{testCase.detail}</span>
                    </div>
                    <span className="test-duration">{testCase.duration || "queued"}</span>
                    <span className="test-status">{testCase.status}</span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "metrics" && (
              <div className="metrics-panel">
                <div className="metrics-note">
                  <span>SEALED SELECTION RESULT · P42 0/9 / 31 LOOPS</span>
                </div>
                <div className="metric-comparison">
                  <div className="metric-head">
                    <span>Metric</span>
                    <span>GPT-5.6-sol</span>
                    <span>Bonsai 27B Q1</span>
                  </div>
                  <div>
                    <span>Selection passes</span>
                    <strong>{latestMetrics.hosted_passed ?? "4"} / 9</strong>
                    <strong>{latestMetrics.bonsai_passed ?? "1"} / 9</strong>
                  </div>
                  <div>
                    <span>Genuine loops</span>
                    <strong>{latestMetrics.hosted_loops ?? "1"}</strong>
                    <strong>{latestMetrics.bonsai_loops ?? "3"}</strong>
                  </div>
                  <div>
                    <span>p95 latency</span>
                    <strong>{latestMetrics.hosted_p95_latency ?? "21.5"} s</strong>
                    <strong>{latestMetrics.bonsai_p95_latency ?? "63.8"} s</strong>
                  </div>
                  <div>
                    <span>Hard gates</span>
                    <strong>FAIL</strong>
                    <strong>FAIL</strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default function App() {
  const [workspace, setWorkspace] = useState(fallbackWorkspace);
  const [selectedAgentId, setSelectedAgentId] = useState("discord-agent");
  const [activeView, setActiveView] = useState("loop");
  const [mobileView, setMobileView] = useState("workflow");
  const [selectedProcess, setSelectedProcess] = useState(null);
  const [consoleTab, setConsoleTab] = useState("events");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState([]);
  const [events, setEvents] = useState([]);
  const [tests, setTests] = useState(
    fallbackWorkspace.testCases.map((testCase) => ({ ...testCase, status: "pending" })),
  );
  const [runStatus, setRunStatus] = useState("ready");
  const [runId, setRunId] = useState("");
  const [error, setError] = useState("");
  const sourceRef = useRef(null);
  const completionRef = useRef(false);

  useEffect(() => {
    const loadWorkspace = async () => {
      try {
        const response = await fetch("/api/workspace");
        if (!response.ok) throw new Error("Workspace unavailable");
        const data = await response.json();
        setWorkspace(data);
        setTests(data.testCases.map((testCase) => ({ ...testCase, status: "pending" })));
        if (!data.agents.some((agent) => agent.id === selectedAgentId)) {
          setSelectedAgentId(data.agents[0]?.id || "");
        }
      } catch {
        setError("Using the local reference workspace because the workspace API is unavailable.");
      }
    };

    loadWorkspace();
    return () => sourceRef.current?.close();
  }, []);

  const selectedAgent =
    workspace.agents.find((agent) => agent.id === selectedAgentId) || workspace.agents[0];
  const currentEvent = events.at(-1);
  const progress = currentEvent?.progress || 0;
  const activeNode = currentEvent?.node || "observe";
  const activeJourneyIndex = journeyToIndex(activeNode, runStatus);
  const latestMetrics = useMemo(
    () =>
      events.reduce(
        (aggregate, event) => ({ ...aggregate, ...(event.metrics || {}) }),
        {},
      ),
    [events],
  );

  const resetTests = () => {
    setTests(workspace.testCases.map((testCase) => ({ ...testCase, status: "pending" })));
  };

  const appendCompletionMessage = (event) => {
    if (completionRef.current) return;
    completionRef.current = true;
    setMessages((current) => [
      ...current,
      {
        id: `${event.run_id}-summary`,
        role: "assistant",
        text: `Replay complete. Hosted passed ${event.metrics?.hosted_passed || 4}/9, untouched Bonsai passed ${event.metrics?.bonsai_passed || 1}/9, and no replacement qualified.`,
        meta: `SEALED RUN ${event.run_id} / NOT YET`,
      },
    ]);
  };

  const startRun = async (promptOverride) => {
    const message = String(promptOverride || draft).trim();
    if (!message || runStatus === "running" || !selectedAgent) return;

    sourceRef.current?.close();
    completionRef.current = false;
    setEvents([]);
    resetTests();
    setRunStatus("running");
    setError("");
    setDraft("");
    setActiveView("loop");
    setSelectedProcess(null);
    setConsoleTab("events");
    setMessages((current) => [
      ...current,
      {
        id: `user-${Date.now()}`,
        role: "user",
        text: message,
        meta: `ASSISTANT · ${selectedAgent.name}`,
      },
    ]);

    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, agentId: selectedAgent.id }),
      });
      if (!response.ok) throw new Error("Could not create run");
      const data = await response.json();
      setRunId(data.runId);

      const source = new EventSource(data.streamUrl);
      sourceRef.current = source;

      source.addEventListener("workflow", (streamEvent) => {
        const event = JSON.parse(streamEvent.data);
        setEvents((current) => [...current, event]);
        if (event.test) {
          setTests((current) =>
            current.map((testCase) =>
              testCase.id === event.test.id ? { ...testCase, ...event.test } : testCase,
            ),
          );
        }
        if (event.event_type === "RUN_COMPLETED" && event.status === "completed") {
          setRunStatus("completed");
          appendCompletionMessage(event);
          source.close();
        }
      });

      source.addEventListener("end", () => source.close());
      source.onerror = () => {
        if (!completionRef.current) {
          setRunStatus("error");
          setError("The event stream closed before the run completed.");
        }
        source.close();
      };
    } catch (runError) {
      setRunStatus("error");
      setError(runError.message || "The run could not be started.");
    }
  };

  const stopRun = () => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setRunStatus("stopped");
    setMessages((current) => [
      ...current,
      {
        id: `stopped-${Date.now()}`,
        role: "assistant",
        text: "Run stopped. No repository or production changes were applied.",
        meta: runId ? `RUN ${runId} / STOPPED` : "RUN / STOPPED",
      },
    ]);
  };

  const newRun = () => {
    sourceRef.current?.close();
    sourceRef.current = null;
    completionRef.current = false;
    setEvents([]);
    resetTests();
    setMessages([]);
    setRunStatus("ready");
    setRunId("");
    setDraft("");
    setError("");
    setConsoleTab("events");
    setSelectedProcess(null);
  };

  if (!selectedAgent) return null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">WD</span>
          <div>
            <strong>WORK DISTILL</strong>
            <span>DISCORD → BONSAI</span>
          </div>
        </div>
        <div className="mobile-view-switch">
          <button
            className={mobileView === "agents" ? "active" : ""}
            onClick={() => setMobileView("agents")}
            type="button"
            aria-pressed={mobileView === "agents"}
          >
            Start
          </button>
          <button
            className={mobileView === "workflow" ? "active" : ""}
            onClick={() => setMobileView("workflow")}
            type="button"
            aria-pressed={mobileView === "workflow"}
          >
            Workflow
          </button>
          {runStatus === "running" ? (
            <button
              className="mobile-stop-button"
              onClick={stopRun}
              type="button"
              aria-label="Stop active run"
            >
              <CircleStop size={12} />
              Stop
            </button>
          ) : (
            <button onClick={newRun} type="button" aria-label="Start new run">
              <Plus size={12} />
              New
            </button>
          )}
        </div>
        <div className="topbar-actions">
          <span className="demo-badge">SEALED EVIDENCE · 10×</span>
          <button className="new-run-button" type="button" onClick={newRun}>
            <Plus size={14} />
            Start over
          </button>
        </div>
      </header>

      <div className={`work-area mobile-${mobileView}`}>
        <ChatPanel
          agents={workspace.agents}
          selectedAgentId={selectedAgentId}
          onSelectAgent={setSelectedAgentId}
          messages={messages}
          runStatus={runStatus}
          draft={draft}
          setDraft={setDraft}
          onSubmit={startRun}
          onStop={stopRun}
        />

        <main className="workspace">
          <div className="workspace-header">
            <div className="selected-title">
              <div>
                <span className="eyebrow">AGENT</span>
                <h1>{selectedAgent.name}</h1>
              </div>
            </div>

            <div className="view-tabs" aria-label="Workspace views">
              <button
                className={activeView === "loop" ? "active" : ""}
                onClick={() => setActiveView("loop")}
                type="button"
                aria-pressed={activeView === "loop"}
              >
                <Activity size={13} />
                Overview
              </button>
              <button
                className={activeView === "contract" ? "active" : ""}
                onClick={() => setActiveView("contract")}
                type="button"
                aria-pressed={activeView === "contract"}
              >
                <Terminal size={13} />
                Technical
              </button>
              <button
                className={activeView === "inventory" ? "active" : ""}
                onClick={() => setActiveView("inventory")}
                type="button"
                aria-pressed={activeView === "inventory"}
              >
                <Search size={13} />
                Assistants
              </button>
            </div>

            <div className="run-state" role="status" aria-live="polite">
              <span className={`run-state-dot ${runStatus}`} />
              <div>
                <span>STATUS</span>
                <strong>
                  {runStatus === "running"
                    ? "Working"
                    : runStatus === "completed"
                      ? "Complete"
                      : runStatus === "stopped"
                        ? "Stopped"
                        : "Ready"}
                </strong>
              </div>
            </div>
          </div>

          {error && <div className="error-banner" role="alert">{error}</div>}

          <div className={`workspace-content ${activeView === "loop" ? "loop-focus" : ""}`}>
            <section className="primary-view">
              {activeView === "loop" && (
                <>
                  <div className="workflow-intro">
                    <div className="loop-header">
                      <div>
                        <span className="eyebrow">MODEL COMPARISON</span>
                        <h3>How the sealed run reached NOT YET</h3>
                      </div>
                    </div>
                    <OuterPhases
                      activeIndex={activeJourneyIndex}
                      runStatus={runStatus}
                    />
                  </div>
                  <LoopGraph
                    activeNode={activeNode}
                    runStatus={runStatus}
                    tests={tests}
                    events={events}
                    currentEvent={currentEvent}
                    selectedProcess={selectedProcess}
                    onSelectProcess={setSelectedProcess}
                    candidateModel={selectedAgent.target}
                  />
                </>
              )}
              {activeView === "inventory" && (
                <InventoryView
                  agents={workspace.agents}
                  selectedAgentId={selectedAgentId}
                  onSelectAgent={setSelectedAgentId}
                  runStatus={runStatus}
                />
              )}
              {activeView === "contract" && <ContractView agent={selectedAgent} />}
            </section>

            {activeView !== "loop" && (
              <Inspector
                agent={selectedAgent}
                currentEvent={currentEvent}
                runStatus={runStatus}
                progress={progress}
                tests={tests}
                events={events}
                runId={runId}
                selectedProcess={selectedProcess}
              />
            )}
          </div>

          <EventConsole
            activeTab={consoleTab}
            setActiveTab={setConsoleTab}
            events={events}
            tests={tests}
            latestMetrics={latestMetrics}
            runStatus={runStatus}
          />
        </main>
      </div>
    </div>
  );
}
