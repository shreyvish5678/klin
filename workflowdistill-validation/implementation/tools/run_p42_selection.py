#!/usr/bin/env python3
"""Evaluate the existing p42 Bonsai adapter on the frozen selection suite."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from benchmark_runner import (
    SuitePolicy,
    VisibleBenchmarkRunner,
    tool_specs_from_surface,
    write_suite_artifacts,
)
from model_backends import OpenAICompatibleChatBackend
from run_official_visible import authorization_factory, executor_factory
from workflowdistill_state import RUN_DIR, append_event, load_state


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = RUN_DIR / "experiments" / "EXP-P42-SELECTION" / "results"


async def run() -> dict:
    state = load_state()
    if state["phase"] != "RUN_ADAPTIVE_RESEARCH":
        raise SystemExit(f"p42 experiment cannot run in phase {state['phase']}")

    def backend_factory(
        _case: dict,
        _repetition: int,
    ) -> OpenAICompatibleChatBackend:
        return OpenAICompatibleChatBackend(
            model_id="Bonsai-27B-Q1_0+p42-f16",
            timeout_seconds=120,
            temperature=0,
        )

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    runner = VisibleBenchmarkRunner(
        suite_id="p42-selection-v1",
        run_id=state["run_id"],
        source_revision=revision,
        system_prompt=(
            RUN_DIR / "artifacts" / "harness" / "immutable-instructions.draft.md"
        ).read_text(encoding="utf-8"),
        tool_specs=tool_specs_from_surface(
            RUN_DIR / "benchmarks" / "draft-tool-surface.json"
        ),
        backend_factory=backend_factory,
        tool_executor_factory=executor_factory,
        authorization_factory=authorization_factory,
        policy=SuitePolicy(
            allowed_splits=frozenset({"selection"}),
            require_frozen_manifest=True,
            repetitions=1,
            run_classification="OFFICIAL_VISIBLE_EVALUATION",
            execution_boundary="local",
        ),
        contract_sha256=state["replacement_contract"]["sha256"],
        research_started_at=state["budget"]["research_started_at"],
    )
    result = await runner.run(RUN_DIR / "benchmarks" / "manifest.json")
    result.summary["provider_cost_status"] = "LOCAL_NO_PROVIDER_FEE"
    result.summary["adapter_sha256"] = (
        "d8ed4c172c8d395e5dbab80a6d05759ab058345911260b0131f1b25ad2975f57"
    )
    write_suite_artifacts(OUTPUT, result)

    state = load_state()
    passed = result.summary["passed_case_count"]
    hard = result.summary["hard_gates_pass"]
    event_type = "EXPERIMENT_COMPLETED" if hard and passed >= 4 else "EXPERIMENT_FAILED"
    state["progress_percent"] = 72
    state["next_action"] = (
        "lock and validate p42 candidate"
        if hard and passed >= 4
        else "record infeasibility and preserve hosted rollback"
    )
    event = append_event(
        state,
        event_type=event_type,
        summary=f"p42 adapter selection result: {passed}/9",
        reason=(
            "The existing hashed adapter was evaluated with only the model "
            "boundary changed from the untouched Bonsai baseline."
        ),
        phase="RUN_ADAPTIVE_RESEARCH",
        status="running",
        lane="B",
        hypothesis_id="H-ADAPTER-P42",
        experiment_id="EXP-P42-SELECTION",
        candidate_id="bonsai-heretic-p42-lora",
        evidence_paths=[
            "experiments/EXP-P42-SELECTION/results/summary.json",
            "experiments/EXP-P42-SELECTION/results/provenance.json",
        ],
        metrics={
            "passed_cases": passed,
            "case_count": 9,
            "hard_gates_pass": hard,
            "p95_latency_ms": result.summary["latency_ms"]["p95"],
            "genuine_repetition_loops": result.summary["metric_totals"][
                "genuine_repetition_loops"
            ],
        },
        actual_cost=0,
        estimated_step_completion_seconds=120,
    )
    return event


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), sort_keys=True))
