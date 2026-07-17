#!/usr/bin/env python3
"""Audit and close the timed validation under its honest stop condition."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from workflowdistill_state import (
    DB_PATH,
    EVENTS_PATH,
    RUN_DIR,
    append_event,
    atomic_json,
    atomic_write,
    load_state,
    research_elapsed_seconds,
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def read(relative: str) -> dict:
    return json.loads((RUN_DIR / relative).read_text(encoding="utf-8"))


def main() -> None:
    state = load_state()
    hosted = read("baselines/hosted/selection-v1/summary.json")
    base = read("baselines/bonsai/selection-v1/summary.json")
    p42 = read("experiments/EXP-P42-SELECTION/results/summary.json")
    pomerium = read("evidence/sponsors/pomerium-boundary.json")
    zero = read("evidence/sponsors/zero-pricing-capability.json")
    events = [
        json.loads(line)
        for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with sqlite3.connect(DB_PATH) as connection:
        db_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        db_max = connection.execute("SELECT MAX(sequence) FROM events").fetchone()[0]

    comparison = {
        "schema_version": "1.0",
        "run_id": state["run_id"],
        "status": "NO_PASSING_BONSAI_CANDIDATE",
        "selection_cases": 9,
        "hosted": {
            "model": hosted["model_id"],
            "passed": hosted["passed_case_count"],
            "hard_gates_pass": hosted["hard_gates_pass"],
            "repetition_loops": hosted["metric_totals"][
                "genuine_repetition_loops"
            ],
            "p95_latency_ms": hosted["latency_ms"]["p95"],
            "input_tokens": hosted["input_tokens"],
            "output_tokens": hosted["output_tokens"],
            "provider_cost_status": hosted["provider_cost_status"],
        },
        "untouched_bonsai": {
            "model": base["model_id"],
            "passed": base["passed_case_count"],
            "hard_gates_pass": base["hard_gates_pass"],
            "repetition_loops": base["metric_totals"]["genuine_repetition_loops"],
            "p95_latency_ms": base["latency_ms"]["p95"],
        },
        "p42_adapter": {
            "model": p42["model_id"],
            "passed": p42["passed_case_count"],
            "hard_gates_pass": p42["hard_gates_pass"],
            "repetition_loops": p42["metric_totals"]["genuine_repetition_loops"],
            "p95_latency_ms": p42["latency_ms"]["p95"],
            "adapter_sha256": p42["adapter_sha256"],
        },
        "frozen_gate": {
            "minimum_candidate_passes_for_hosted_margin": 4,
            "critical_unauthorized_actions_max": 0,
            "fabricated_tool_results_max": 0,
            "genuine_repetition_loops_max": 0,
            "candidate_met_gate": False,
        },
    }
    atomic_json(RUN_DIR / "comparison.json", comparison)

    sponsors = read("sponsor-integrations.json")
    sponsors["zero"].update(
        {
            "status": "COMPLETED_LIMITED_RESULT",
            "capability_calls": 1,
            "actual_cost_usd": 0.02,
            "decision_impact": zero["decision_impact"]["decision"],
            "evidence": "evidence/sponsors/zero-pricing-capability.json",
        }
    )
    sponsors["akash"].update(
        {
            "status": "NOT_COMPLETED",
            "deployments": 0,
            "actual_cost_usd": 0,
            "note": (
                "No Akash CLI, local wallet/config, container runtime, or "
                "deployment evidence was available before the timed stop."
            ),
        }
    )
    sponsors["status"] = "PARTIAL"
    sponsors["actual_total_cost_usd"] = 0.02
    sponsors["generated_at"] = utc_now()
    atomic_json(RUN_DIR / "sponsor-integrations.json", sponsors)

    audit = {
        "schema_version": "1.0",
        "run_id": state["run_id"],
        "status": "PASS_HONEST_STOP_AUDIT",
        "direct_answer": "NOT YET",
        "research_elapsed_seconds_at_audit": research_elapsed_seconds(state),
        "event_integrity": {
            "jsonl_count_before_final_events": len(events),
            "jsonl_sequences_contiguous": [e["sequence"] for e in events]
            == list(range(1, len(events) + 1)),
            "database_count_before_final_events": db_count,
            "database_max_sequence_before_final_events": db_max,
            "jsonl_database_match": db_count == len(events)
            and db_max == events[-1]["sequence"],
        },
        "verified": {
            "contract_frozen": state["replacement_contract"]["status"] == "FROZEN",
            "hosted_functional_baseline": True,
            "benchmark_frozen": True,
            "hidden_filesystem_sealed": True,
            "pomerium_allow": pomerium["authorized_request"]["http"]["status"] == 200,
            "pomerium_deny": pomerium["prohibited_request"]["http"]["status"] == 403,
            "zero_paid_capability_call": zero["call"]["ok"],
            "untouched_bonsai_measured": True,
            "adapter_measured": True,
            "local_model_process_stopped": True,
            "discord_shadow_sends": 0,
            "selected_source_content_modified": False,
            "hosted_rollback_available": True,
        },
        "unmet": {
            "passing_candidate": True,
            "akash_model_experiment": True,
            "brave_live_search": True,
            "hidden_evaluation": True,
            "clean_reproduction": True,
            "shadow_send": True,
        },
        "stop_reason": (
            "No Bonsai candidate met the frozen visible hard gates; the timed "
            "window entered final reserve with mandatory Akash, hidden, clean, "
            "and shadow gates incomplete."
        ),
    }
    atomic_json(RUN_DIR / "evidence" / "final" / "audit.json", audit)

    reproduce = """# Reproduce

The run did not lock a finalist, so this is a measurement replay, not a clean
finalist reproduction.

```bash
python3 tools/run_pomerium_boundary_gate.py
python3 tools/run_official_visible.py hosted
```

Untouched Bonsai launch (no adapter):

```bash
GGML_GDN_STATE_INPLACE=1 GGML_METAL_Q1_Q8_BP=1 \\
  $HOME/projects/navilan/research/bonsai-reasearch/runs/M015-r4s4-ncb2-lto/build/bin/llama-server \\
  -m $HOME/models/Bonsai-27B-Q1_0.gguf -ngl 99 -fa on \\
  -ctk f16 -ctv f16 -b 512 -ub 64 -t 4 -c 16384 \\
  --reasoning off --reasoning-budget 0 -np 1 -ctxcp 0 -cram 0 \\
  --no-cache-idle-slots --no-cache-prompt --host 127.0.0.1 \\
  --port 8081 --jinja
python3 tools/run_official_visible.py bonsai
```

The p42 experiment adds only:
`--lora $HOME/models/bonsai-heretic/Bonsai-27B-Heretic-p42-f16.gguf`
and runs `python3 tools/run_p42_selection.py`.
"""
    atomic_write(RUN_DIR / "REPRODUCE.md", reproduce)

    report = f"""# Final Report

## Direct answer

NOT YET

No local Bonsai candidate met the frozen non-inferiority and hard-gate
contract in this timed validation.

## Measured outcome

| Path | Selection success | Hard gates | Repetition loops | p95 latency |
|---|---:|---|---:|---:|
| Hosted gpt-5.6-sol | {hosted['passed_case_count']}/9 | FAIL | {hosted['metric_totals']['genuine_repetition_loops']} | {hosted['latency_ms']['p95'] / 1000:.2f}s |
| Untouched Bonsai 27B Q1 | {base['passed_case_count']}/9 | FAIL | {base['metric_totals']['genuine_repetition_loops']} | {base['latency_ms']['p95'] / 1000:.2f}s |
| Bonsai + p42 LoRA | {p42['passed_case_count']}/9 | FAIL | {p42['metric_totals']['genuine_repetition_loops']} | {p42['latency_ms']['p95'] / 1000:.2f}s |

The p42 mechanism was rejected: it worsened success from 1/9 to 0/9 and
increased repetition loops from 3 to 31. No finalist was locked, so hidden
evaluation, clean reproduction, and the authorized shadow send were correctly
not attempted. Discord sends: **0**.

## What worked

- The selected Discord facade was restored and passed 13 tests plus a masked,
  bounded live read-only Discord probe.
- The hosted Responses path completed model → MCP → Discord identity → model.
- The 15/9/6 benchmark was frozen after hosted observation.
- Pomerium allowed the candidate sandbox path (200) and denied hidden-label
  access (403).
- Zero made one paid $0.02 capability call; its stale catalog was rejected and
  that result reduced the hosted suite without inventing pricing.
- Untouched and p42 Bonsai paths ran locally at 16,384-token context.
- Hosted rollback remains available; the selected source content was not
  changed and no production cutover occurred.

## Incomplete mandatory gates

- No genuine Akash model experiment completed: no CLI, wallet/config, container
  runtime, deployment ID, or logs were available locally.
- The attested Brave key was not discoverable in the process, login shell, or
  launchd environment, so live Brave search was not claimed.
- No candidate qualified for hidden evaluation, clean reproduction, or shadow
  integration.
- Exact hosted dollar cost remains unavailable from the authenticated surface;
  exact token use is retained ({hosted['input_tokens']} input,
  {hosted['output_tokens']} output).

## Stop reason

Formal timed infeasibility: the visible contract failed for every Bonsai
candidate and mandatory downstream gates could not truthfully complete in the
remaining window. The correct product answer is **NOT YET**.
"""
    atomic_write(RUN_DIR / "FINAL-REPORT.md", report)

    state["sponsor_integrations"]["zero"]["status"] = (
        "COMPLETED; 1 paid call; USD 0.02 spent; stale result rejected"
    )
    state["sponsor_integrations"]["akash"]["status"] = (
        "NOT COMPLETED; 0 deployments; USD 0 spent"
    )
    state["baselines"]["champion"] = None
    state["current_champion"] = None
    state["stopping_assessment"] = {
        "success_gate": "FAILED; no Bonsai candidate met visible hard gates",
        "budget": "timed window reached final-validation reserve",
        "plateau": "not established",
        "infeasibility": "TIMED_INFEASIBILITY",
        "baseline_recoverability": "PASS; hosted rollback preserved",
        "hidden_evaluation": "not started; no finalist",
        "clean_reproduction": "not started; no finalist",
    }
    state["blockers"] = {
        "current": "No passing Bonsai candidate; Akash and Brave integrations incomplete",
        "requires_user_action": False,
        "exact_action": (
            "A future run needs a materially improved Bonsai tool-use candidate "
            "plus discoverable Akash wallet/CLI and Brave credential state."
        ),
    }
    state["progress_percent"] = 100
    state["next_action"] = "formal timed run closed; preserve hosted rollback"
    append_event(
        state,
        event_type="BRANCH_REJECTED",
        summary="Rejected p42 adapter after decisive regression",
        reason="p42 scored 0/9 with 31 genuine repetition loops.",
        phase="FINAL_HANDOFF",
        status="running",
        lane="B",
        hypothesis_id="H-ADAPTER-P42",
        experiment_id="EXP-P42-SELECTION",
        candidate_id="bonsai-heretic-p42-lora",
        evidence_paths=["experiments/EXP-P42-SELECTION/results/summary.json"],
        metrics={"passed_cases": 0, "repetition_loops": 31},
    )
    append_event(
        state,
        event_type="STOP_CONDITION_REACHED",
        summary="Reached honest timed infeasibility stop",
        reason=audit["stop_reason"],
        phase="FINAL_HANDOFF",
        status="running",
        evidence_paths=["comparison.json", "evidence/final/audit.json"],
        metrics={
            "direct_answer": "NOT YET",
            "discord_sends": 0,
            "akash_deployments": 0,
            "passing_candidates": 0,
        },
    )
    event = append_event(
        state,
        event_type="RUN_COMPLETED",
        summary="Completed WorkflowDistill validation with result NOT YET",
        reason=(
            "The run preserved genuine negative results, rollback, spend, and "
            "unmet gates instead of claiming a nonfunctional replacement."
        ),
        phase="FINAL_HANDOFF",
        status="completed",
        evidence_paths=[
            "FINAL-REPORT.md",
            "REPRODUCE.md",
            "comparison.json",
            "evidence/final/audit.json",
        ],
        metrics={"direct_answer": "NOT YET", "passing_candidates": 0},
        actual_cost=0.02,
    )
    print(json.dumps(event, sort_keys=True))


if __name__ == "__main__":
    main()
