#!/usr/bin/env python3
"""Run the frozen selection suite through hosted or local model boundaries."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from benchmark_runner import (
    FixtureToolExecutor,
    SuitePolicy,
    VisibleBenchmarkRunner,
    tool_specs_from_surface,
    write_suite_artifacts,
)
from model_backends import CodexExecBackend, OpenAICompatibleChatBackend
from model_harness import AuthorizationContext
from workflowdistill_state import RUN_DIR, append_event, load_state


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = RUN_DIR / "benchmarks" / "manifest.json"
TOOL_SURFACE = RUN_DIR / "benchmarks" / "draft-tool-surface.json"
SYSTEM_PROMPT = (
    RUN_DIR / "artifacts" / "harness" / "immutable-instructions.draft.md"
)


class OfficialFixtureExecutor(FixtureToolExecutor):
    """Frozen fixtures plus the model-neutral synthetic send transaction."""

    def __init__(self, case: dict[str, Any]) -> None:
        super().__init__(case.get("context", {}).get("tool_fixtures", []))
        self.context = copy.deepcopy(case.get("context", {}))

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name != "send_dm":
            return await super().call(name, arguments)
        self.calls.append((name, copy.deepcopy(arguments)))
        if arguments.get("confirm_send") is True:
            return {"sent": True, "message_id": "synthetic-message-id"}
        receipt = self.context.get(
            "synthetic_dry_run_receipt",
            "synthetic-visible-suite-receipt",
        )
        return {
            "sent": False,
            "dry_run": True,
            "confirmation_token": receipt,
        }


def executor_factory(
    case: dict[str, Any],
    _repetition: int,
) -> OfficialFixtureExecutor:
    return OfficialFixtureExecutor(case)


def authorization_factory(
    case: dict[str, Any],
    _repetition: int,
) -> AuthorizationContext | None:
    synthetic = case.get("context", {}).get("synthetic_authorization")
    if not isinstance(synthetic, dict):
        return None
    committed = [
        call
        for call in case["expectations"]["tool_calls"]
        if call["name"] == "send_dm"
        and call["arguments"].get("confirm_send") is True
    ]
    if len(committed) != 1:
        raise ValueError("Synthetic send authorization requires one committed call")
    arguments = committed[0]["arguments"]
    return AuthorizationContext(
        allow_send_commit=True,
        channel_id=str(arguments["channel_id"]),
        content=str(arguments["content"]),
    )


def source_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


async def run(kind: str, endpoint: str) -> dict[str, Any]:
    state = load_state()
    expected_phase = (
        "MEASURE_HOSTED_BASELINE"
        if kind == "hosted"
        else "MEASURE_BONSAI_BASELINE"
    )
    if state["phase"] != expected_phase:
        raise SystemExit(
            f"{kind} selection suite requires {expected_phase}, got {state['phase']}"
        )
    suite_id = f"{kind}-selection-v1"
    output = RUN_DIR / "baselines" / kind / "selection-v1"
    if output.exists():
        raise SystemExit(f"Official output already exists: {output}")

    start_event = (
        "HOSTED_BASELINE_STARTED"
        if kind == "hosted"
        else "BONSAI_BASELINE_STARTED"
    )
    append_event(
        state,
        event_type=start_event,
        summary=f"Started official frozen {kind} selection measurement",
        reason=(
            "The same frozen nine-case selection set, immutable tool surface, "
            "orchestration harness, fixtures, and evaluator are used for both paths."
        ),
        phase=expected_phase,
        status="running",
        lane="A" if kind == "hosted" else "B",
        candidate_id=None if kind == "hosted" else "bonsai-27b-q1-base",
        evidence_paths=["benchmarks/manifest.json"],
        metrics={"selection_cases": 9, "hidden_labels_loaded": False},
        estimated_step_completion_seconds=420,
    )

    if kind == "hosted":
        def backend_factory(
            _case: dict[str, Any],
            _repetition: int,
        ) -> CodexExecBackend:
            return CodexExecBackend(
                model_id="gpt-5.6-sol",
                reasoning_effort="medium",
                timeout_seconds=120,
            )

        execution_boundary = "external_hosted"
    else:
        def backend_factory(
            _case: dict[str, Any],
            _repetition: int,
        ) -> OpenAICompatibleChatBackend:
            return OpenAICompatibleChatBackend(
                model_id="Bonsai-27B-Q1_0",
                endpoint=endpoint,
                timeout_seconds=120,
                temperature=0,
            )

        execution_boundary = "local"

    runner = VisibleBenchmarkRunner(
        suite_id=suite_id,
        run_id=state["run_id"],
        source_revision=source_revision(),
        system_prompt=SYSTEM_PROMPT.read_text(encoding="utf-8"),
        tool_specs=tool_specs_from_surface(TOOL_SURFACE),
        backend_factory=backend_factory,
        tool_executor_factory=executor_factory,
        authorization_factory=authorization_factory,
        policy=SuitePolicy(
            allowed_splits=frozenset({"selection"}),
            require_frozen_manifest=True,
            repetitions=1,
            run_classification="OFFICIAL_VISIBLE_EVALUATION",
            execution_boundary=execution_boundary,
        ),
        contract_sha256=state["replacement_contract"]["sha256"],
        research_started_at=state["budget"]["research_started_at"],
    )
    result = await runner.run(MANIFEST)
    result.summary["provider_cost_status"] = (
        "UNAVAILABLE_FROM_CURRENT_AUTH_SURFACE"
        if kind == "hosted"
        else "LOCAL_NO_PROVIDER_FEE"
    )
    result.summary["fixture_boundary"] = (
        "synthetic private-safe deterministic tools; no Discord writes"
    )
    write_suite_artifacts(output, result)

    state = load_state()
    completed_event = (
        "HOSTED_BASELINE_COMPLETED"
        if kind == "hosted"
        else "BONSAI_BASELINE_COMPLETED"
    )
    state["baselines"][kind] = {
        "status": "OFFICIAL_SELECTION_COMPLETED",
        "model": result.summary["model_id"],
        "backend": result.summary["backend_id"],
        "passed": result.summary["passed_case_count"],
        "cases": result.summary["case_count"],
        "hard_gates_pass": result.summary["hard_gates_pass"],
        "p95_latency_ms": result.summary["latency_ms"]["p95"],
        "input_tokens": result.summary["input_tokens"],
        "output_tokens": result.summary["output_tokens"],
        "provider_cost_usd": result.summary["provider_cost_usd"],
        "provider_cost_status": result.summary["provider_cost_status"],
        "evidence": str(output.relative_to(RUN_DIR) / "summary.json"),
    }
    if kind == "hosted":
        state["progress_percent"] = 55
        state["next_action"] = "launch untouched Bonsai and run matched selection"
        next_phase = "MEASURE_BONSAI_BASELINE"
    else:
        state["progress_percent"] = 65
        state["next_action"] = "compare candidates and run material improvement"
        next_phase = "RUN_ADAPTIVE_RESEARCH"
    event = append_event(
        state,
        event_type=completed_event,
        summary=f"Completed official frozen {kind} selection measurement",
        reason=(
            "The official selection suite completed through the shared immutable "
            "agent path with normalized traces and deterministic scores."
        ),
        phase=next_phase,
        status="running",
        lane="A" if kind == "hosted" else "B",
        candidate_id=None if kind == "hosted" else "bonsai-27b-q1-base",
        evidence_paths=[
            str(output.relative_to(RUN_DIR) / "summary.json"),
            str(output.relative_to(RUN_DIR) / "provenance.json"),
        ],
        metrics={
            "passed_cases": result.summary["passed_case_count"],
            "case_count": result.summary["case_count"],
            "hard_gates_pass": result.summary["hard_gates_pass"],
            "p95_latency_ms": result.summary["latency_ms"]["p95"],
            "input_tokens": result.summary["input_tokens"],
            "output_tokens": result.summary["output_tokens"],
            "discord_writes": 0,
        },
        actual_cost=result.summary["provider_cost_usd"],
        estimated_step_completion_seconds=360,
    )
    return event


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("hosted", "bonsai"))
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8081/v1/chat/completions",
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.kind, args.endpoint)), sort_keys=True))


if __name__ == "__main__":
    main()
