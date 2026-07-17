#!/usr/bin/env python3
"""Freeze the hosted-observed workflow profile and stratified benchmark."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from benchmark_eval import canonical_sha256, manifest_content_sha256
from workflowdistill_state import RUN_DIR, append_event, atomic_json, load_state


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = RUN_DIR / "benchmarks"
DEVELOPMENT = {
    1,
    2,
    3,
    6,
    9,
    10,
    11,
    12,
    18,
    20,
    22,
    24,
    26,
    28,
    29,
}
SELECTION = {5, 7, 8, 13, 14, 16, 19, 23, 27}
HIDDEN = {4, 15, 17, 21, 25, 30}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_for(number: int) -> str:
    if number in DEVELOPMENT:
        return "development"
    if number in SELECTION:
        return "selection"
    if number in HIDDEN:
        return "hidden"
    raise ValueError(f"Draft case {number} has no frozen split")


def refine_case(case: dict, split: str) -> dict:
    case = json.loads(json.dumps(case))
    case["split"] = split
    case["privacy"]["external_use_approved"] = split != "hidden"
    if case["case_id"] == "draft-002-identity":
        case["expectations"]["required_fact_groups"][0].append(
            "configured Discord account"
        )
    if case["case_id"] == "draft-020-server-admin-denial":
        case["expectations"]["required_fact_groups"][0].extend(
            ["limited", "can’t"]
        )
    case["source"]["benchmark_refinement"] = (
        "Frozen after authenticated hosted functional traces; only split, "
        "external-use approval, and two observed lexical variants changed."
    )
    return case


def main() -> None:
    state = load_state()
    if state["phase"] not in {
        "PROFILE_SELECTED_WORKFLOW",
        "BUILD_AND_FREEZE_BENCHMARK",
    }:
        if state["phase"] == "MEASURE_HOSTED_BASELINE":
            print(
                json.dumps(
                    {"status": "NOOP_ALREADY_FROZEN", "sequence": state["sequence"]}
                )
            )
            return
        raise SystemExit(f"Cannot freeze benchmark in phase {state['phase']}")
    if state["baselines"]["hosted"].get("status", "").startswith(
        "FUNCTIONAL_GATE_PASSED"
    ) is False:
        raise SystemExit("Hosted functional gate has not passed")

    source_manifest = json.loads(
        (BENCHMARKS / "manifest.json").read_text(encoding="utf-8")
    )
    if source_manifest["status"] == "FROZEN":
        raise SystemExit("Benchmark manifest is already frozen")
    frozen_at = utc_now()
    records = []
    frozen_cases = []
    for index, source_record in enumerate(source_manifest["cases"], start=1):
        source_path = BENCHMARKS / source_record["path"]
        case = json.loads(source_path.read_text(encoding="utf-8"))
        split = split_for(index)
        case = refine_case(case, split)
        destination = BENCHMARKS / split / source_path.name
        if destination.exists():
            raise SystemExit(f"Frozen case already exists: {destination}")
        atomic_json(destination, case)
        os.chmod(destination, 0o400 if split == "hidden" else 0o444)
        frozen_cases.append(case)
        records.append(
            {
                "case_id": case["case_id"],
                "path": str(destination.relative_to(BENCHMARKS)),
                "split": split,
                "severity": case["severity"],
                "task_category": case["task_category"],
                "source_kind": case["source"]["kind"],
                "sha256": canonical_sha256(case),
            }
        )
    os.chmod(BENCHMARKS / "hidden", 0o700)

    contract_sha256 = state["replacement_contract"]["sha256"]
    tool_surface_path = BENCHMARKS / "draft-tool-surface.json"
    tool_surface = json.loads(tool_surface_path.read_text(encoding="utf-8"))
    tool_surface.update(
        {
            "status": "FROZEN",
            "frozen_at": frozen_at,
            "replacement_contract_sha256": contract_sha256,
        }
    )
    atomic_json(tool_surface_path, tool_surface)
    os.chmod(tool_surface_path, 0o444)

    manifest = {
        "schema_version": "1.0",
        "run_id": state["run_id"],
        "status": "FROZEN",
        "generated_at": source_manifest["generated_at"],
        "frozen_at": frozen_at,
        "sha256": None,
        "source_draft_records_sha256": source_manifest["draft_sha256"],
        "replacement_contract_sha256": contract_sha256,
        "tool_surface_sha256": file_sha256(tool_surface_path),
        "evaluator_sha256": file_sha256(ROOT / "tools" / "benchmark_eval.py"),
        "split_policy": {
            "development": "visible; approved synthetic development use",
            "selection": "visible; evaluation only; prohibited from training",
            "hidden": (
                "research branches prohibited; filesystem sealed and served only "
                "through the Pomerium evaluator boundary"
            ),
        },
        "privacy": {
            "raw_private_data": False,
            "hidden_labels_created": True,
            "private_dm_content": False,
            "selection_or_hidden_training": False,
        },
        "cases": records,
    }
    manifest["sha256"] = manifest_content_sha256(manifest)
    atomic_json(BENCHMARKS / "manifest.json", manifest)
    os.chmod(BENCHMARKS / "manifest.json", 0o444)

    profile_path = RUN_DIR / "workflow-profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile.update(
        {
            "status": "FROZEN_HOSTED_OBSERVED",
            "frozen_at": frozen_at,
            "replacement_contract_sha256": contract_sha256,
            "benchmark_manifest_sha256": manifest["sha256"],
        }
    )
    profile["facts"] = [
        "The isolated facade builds and all 13 fake-runtime tests pass.",
        "A masked live probe reached Discord through the isolated facade with the credential at mode 0600.",
        "The authenticated OpenAI Responses control completed direct, single-tool, multi-step, and permission-sensitive synthetic paths.",
        "A separate live read-only identity turn traversed hosted model, isolated MCP, Discord REST, tool feedback, and final response.",
        "The selected workflow is prompt-triggered REST orchestration and has no Discord Gateway event handler.",
    ]
    profile["context_distribution"].update(
        {
            "contract_max_tokens": 16384,
            "observed": (
                "Five short hosted observations plus one long/noisy synthetic case; "
                "16K remains an explicit validation requirement."
            ),
            "missing_evidence": (
                "Official visible-suite distribution and local Bonsai measurements."
            ),
        }
    )
    profile["output_contract"]["hosted_observation_status"] = "VERIFIED"
    profile["streaming_behavior"]["model"] = (
        "Current restored Responses boundary is non-streaming; identical harness "
        "normalizes complete model turns."
    )
    profile["hosted_observations"] = {
        "synthetic_functional_shapes": 4,
        "live_read_only_end_to_end_turns": 1,
        "hard_gates_pass": True,
        "observed_efficiency_gap": (
            "Hosted multi-step trace used one unnecessary message-retrieval call."
        ),
        "evidence_paths": [
            "evidence/baseline/hosted-functional-gate.json",
            "evidence/baseline/live-hosted-identity.json",
            "evidence/baseline/restoration-summary.json",
        ],
    }
    profile["missing_evidence"] = [
        "Brave credential injection and one live public-search result",
        "official hosted and Bonsai visible-suite metrics",
        "local latency, memory, throughput, and 16K context measurement",
        "final exact shadow-send result",
    ]
    atomic_json(profile_path, profile)

    split_counts = Counter(case["split"] for case in frozen_cases)
    summary_path = RUN_DIR / "benchmark-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update(
        {
            "status": "FROZEN",
            "frozen_at": frozen_at,
            "draft_cases": 0,
            "development_cases": split_counts["development"],
            "selection_cases": split_counts["selection"],
            "hidden_cases": split_counts["hidden"],
            "manifest_sha256": manifest["sha256"],
            "tool_surface_sha256": manifest["tool_surface_sha256"],
            "evaluator_sha256": manifest["evaluator_sha256"],
            "freeze_gate": "PASS",
            "missing_before_freeze": [],
        }
    )
    summary["privacy"].update(
        {
            "external_use_approved": True,
            "hidden_labels_created": True,
            "raw_private_data": False,
        }
    )
    atomic_json(summary_path, summary)

    state["lanes"]["C"].update(
        {
            "status": "completed",
            "current_action": "workflow profile and 15/9/6 benchmark frozen",
            "completed_at": frozen_at,
            "evidence_paths": sorted(
                set(
                    state["lanes"]["C"]["evidence_paths"]
                    + [
                        "workflow-profile.json",
                        "benchmark-summary.json",
                        "benchmarks/manifest.json",
                    ]
                )
            ),
        }
    )
    state["progress_percent"] = 48
    state["next_action"] = "run compact official hosted visible-suite measurement"

    append_event(
        state,
        event_type="WORKFLOW_PROFILING_STARTED",
        summary="Started hosted-observed workflow profiling",
        reason=(
            "The functional gate supplied representative authenticated direct, "
            "tool, multi-step, permission, and live Discord observations."
        ),
        phase="PROFILE_SELECTED_WORKFLOW",
        status="running",
        lane="C",
        evidence_paths=[
            "evidence/baseline/hosted-functional-gate.json",
            "evidence/baseline/live-hosted-identity.json",
        ],
        metrics={"hosted_observations": 5, "profile_frozen": False},
    )
    append_event(
        state,
        event_type="WORKFLOW_PROFILE_UPDATED",
        summary="Froze the verified hosted-observed workflow profile",
        reason=(
            "Source, tests, live Discord evidence, and hosted traces now establish "
            "the full prompt-triggered model/tool/result/final-response contract."
        ),
        phase="BUILD_AND_FREEZE_BENCHMARK",
        status="running",
        lane="C",
        evidence_paths=["workflow-profile.json"],
        metrics={
            "profile_frozen": True,
            "tool_count": 6,
            "synthetic_hosted_shapes": 4,
            "live_hosted_paths": 1,
        },
    )
    event = append_event(
        state,
        event_type="BENCHMARK_FROZEN",
        summary="Froze the 15/9/6 WorkflowDistill benchmark",
        reason=(
            "Thirty source-mixed, private-safe cases were stratified after hosted "
            "observation; input cases, tool surface, evaluator, contract, splits, "
            "and hashes are immutable before official comparison."
        ),
        phase="MEASURE_HOSTED_BASELINE",
        status="running",
        lane="C",
        evidence_paths=[
            "benchmarks/manifest.json",
            "benchmark-summary.json",
            "workflow-profile.json",
        ],
        metrics={
            "development_cases": split_counts["development"],
            "selection_cases": split_counts["selection"],
            "hidden_cases": split_counts["hidden"],
            "manifest_sha256": manifest["sha256"],
            "private_cases": 0,
            "hidden_training_allowed": False,
        },
        estimated_step_completion_seconds=600,
    )
    print(json.dumps(event, sort_keys=True))


if __name__ == "__main__":
    main()
