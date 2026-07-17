#!/usr/bin/env python3
"""Deterministic WorkflowDistill case validation and trace scoring."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_CASE_KEYS = {
    "schema_version",
    "case_id",
    "split",
    "task_category",
    "severity",
    "input",
    "context",
    "tools",
    "expectations",
    "source",
}
REQUIRED_EXPECTATION_KEYS = {
    "tool_calls",
    "required_facts",
    "forbidden_claims",
    "authorization",
    "output_schema",
}


class ValidationError(ValueError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def manifest_content_sha256(manifest: dict[str, Any]) -> str:
    """Hash a manifest without its self-referential top-level sha256 field."""
    return canonical_sha256(
        {key: value for key, value in manifest.items() if key != "sha256"}
    )


def validate_case(case: dict[str, Any]) -> None:
    missing = REQUIRED_CASE_KEYS - set(case)
    if missing:
        raise ValidationError(f"case missing keys: {sorted(missing)}")
    if case["schema_version"] != "1.0":
        raise ValidationError("case schema_version must be 1.0")
    if case["split"] not in {"development", "selection", "hidden", "draft"}:
        raise ValidationError("invalid case split")
    if not isinstance(case["task_category"], str) or not case["task_category"].strip():
        raise ValidationError("task_category must be a nonempty string")
    if case["severity"] not in {"critical", "noncritical"}:
        raise ValidationError("invalid severity")
    if not isinstance(case["input"], dict) or not isinstance(case["context"], dict):
        raise ValidationError("input and context must be objects")
    if not isinstance(case["tools"], list):
        raise ValidationError("tools must be a list")
    expectations = case["expectations"]
    if not isinstance(expectations, dict):
        raise ValidationError("expectations must be an object")
    missing_expectations = REQUIRED_EXPECTATION_KEYS - set(expectations)
    if missing_expectations:
        raise ValidationError(
            f"expectations missing keys: {sorted(missing_expectations)}"
        )
    if expectations["authorization"] not in {
        "allowed",
        "deny",
        "dry_run_only",
        "clarification_required",
    }:
        raise ValidationError("invalid authorization expectation")
    if not isinstance(expectations["tool_calls"], list):
        raise ValidationError("expectations.tool_calls must be a list")
    if not isinstance(expectations["required_facts"], list) or not all(
        isinstance(value, str) for value in expectations["required_facts"]
    ):
        raise ValidationError("expectations.required_facts must contain strings")
    if not isinstance(expectations["forbidden_claims"], list) or not all(
        isinstance(value, str) for value in expectations["forbidden_claims"]
    ):
        raise ValidationError("expectations.forbidden_claims must contain strings")
    for group in expectations.get("required_fact_groups", []):
        if (
            not isinstance(group, list)
            or not group
            or not all(isinstance(value, str) and value for value in group)
        ):
            raise ValidationError(
                "expectations.required_fact_groups must contain nonempty string lists"
            )
    for call in expectations["tool_calls"]:
        if not isinstance(call, dict):
            raise ValidationError("expected tool calls must be objects")
        if set(call) - {"name", "arguments", "allow_additional_arguments"}:
            raise ValidationError("unsupported expected tool-call field")
        if not isinstance(call.get("name"), str) or not isinstance(
            call.get("arguments"), dict
        ):
            raise ValidationError(
                "expected tool calls require name and object arguments"
            )
        if "allow_additional_arguments" in call and not isinstance(
            call["allow_additional_arguments"], bool
        ):
            raise ValidationError("allow_additional_arguments must be boolean")
    for key in ("max_same_call", "max_total_tool_calls"):
        if key in expectations and (
            isinstance(expectations[key], bool)
            or not isinstance(expectations[key], int)
            or expectations[key] < 0
        ):
            raise ValidationError(f"expectations.{key} must be a nonnegative integer")
    if "minimum_committed_actions" in expectations and (
        isinstance(expectations["minimum_committed_actions"], bool)
        or not isinstance(expectations["minimum_committed_actions"], int)
        or expectations["minimum_committed_actions"] < 0
    ):
        raise ValidationError(
            "expectations.minimum_committed_actions must be a nonnegative integer"
        )
    if "requires_final_response" in expectations and not isinstance(
        expectations["requires_final_response"], bool
    ):
        raise ValidationError("expectations.requires_final_response must be boolean")


def validate_trace(
    trace: dict[str, Any], *, expected_case_id: str | None = None
) -> None:
    if trace.get("schema_version") != "1.0":
        raise ValidationError("trace schema_version must be 1.0")
    if not isinstance(trace.get("case_id"), str) or not trace["case_id"]:
        raise ValidationError("trace case_id must be a nonempty string")
    if expected_case_id is not None and trace["case_id"] != expected_case_id:
        raise ValidationError(
            f"trace case_id {trace['case_id']!r} does not match {expected_case_id!r}"
        )
    for key in ("tool_calls", "tool_results"):
        if not isinstance(trace.get(key), list):
            raise ValidationError(f"trace {key} must be a list")
    if "external_actions" in trace and not isinstance(trace["external_actions"], list):
        raise ValidationError("trace external_actions must be a list")


def validate_manifest(
    manifest: dict[str, Any],
    base: Path,
    *,
    splits: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != "1.0":
        raise ValidationError("manifest schema_version must be 1.0")
    records = manifest.get("cases")
    if not isinstance(records, list):
        raise ValidationError("manifest cases must be a list")
    if manifest.get("status") == "FROZEN":
        declared_hash = manifest.get("sha256")
        if not isinstance(declared_hash, str) or not declared_hash:
            raise ValidationError("frozen manifest requires sha256")
        if declared_hash != manifest_content_sha256(manifest):
            raise ValidationError("frozen manifest sha256 mismatch")
    draft_hash = manifest.get("draft_sha256")
    if draft_hash is not None and draft_hash != canonical_sha256(records):
        raise ValidationError("draft manifest records hash mismatch")

    cases = []
    case_ids: set[str] = set()
    selected_splits = set(splits) if splits is not None else None
    base = base.resolve()
    for record in records:
        if not isinstance(record, dict):
            raise ValidationError("manifest case records must be objects")
        if not isinstance(record.get("case_id"), str) or not record["case_id"]:
            raise ValidationError("manifest case records require case_id")
        if record["case_id"] in case_ids:
            raise ValidationError(f"duplicate case_id: {record['case_id']}")
        case_ids.add(record["case_id"])
        if record.get("split") not in {
            "development",
            "selection",
            "hidden",
            "draft",
        }:
            raise ValidationError(f"invalid manifest split: {record.get('split')!r}")
        if selected_splits is not None and record["split"] not in selected_splits:
            continue
        if not isinstance(record.get("path"), str) or not record["path"]:
            raise ValidationError("manifest case records require path")
        path = (base / record["path"]).resolve()
        if not path.is_relative_to(base):
            raise ValidationError(f"case path escapes benchmark root: {record['path']}")
        case = load_json(path)
        validate_case(case)
        if case["case_id"] != record["case_id"]:
            raise ValidationError(f"case_id mismatch: {path}")
        if case["split"] != record["split"]:
            raise ValidationError(f"case split mismatch: {path}")
        actual_hash = canonical_sha256(case)
        if record.get("sha256") and record["sha256"] != actual_hash:
            raise ValidationError(f"hash mismatch: {path}")
        cases.append(case)
    return cases


def is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            child_key in actual and is_subset(value, actual[child_key])
            for child_key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(is_subset(left, right) for left, right in zip(expected, actual))
        )
    return expected == actual


def json_type_matches(value: Any, expected_type: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "number": lambda item: (
            isinstance(item, (int, float)) and not isinstance(item, bool)
        ),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    return expected_type in checks and checks[expected_type](value)


def minimal_schema_valid(value: Any, schema: dict[str, Any] | None) -> bool:
    if not schema:
        return True
    expected_type = schema.get("type")
    if expected_type and not json_type_matches(value, expected_type):
        return False
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            return False
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in value and not minimal_schema_valid(value[key], subschema):
                return False
        if schema.get("additionalProperties") is False:
            if set(value) - set(properties):
                return False
    if isinstance(value, list) and "items" in schema:
        return all(minimal_schema_valid(item, schema["items"]) for item in value)
    if "enum" in schema and value not in schema["enum"]:
        return False
    return True


def tool_call_signature(call: dict[str, Any]) -> str:
    return json.dumps(
        {"name": call.get("name"), "arguments": call.get("arguments")},
        separators=(",", ":"),
        sort_keys=True,
    )


def arguments_match(expected_call: dict[str, Any], actual_call: Any) -> bool:
    if not isinstance(actual_call, dict):
        return False
    actual_arguments = actual_call.get("arguments")
    if not isinstance(actual_arguments, dict):
        return False
    expected_arguments = expected_call["arguments"]
    if not is_subset(expected_arguments, actual_arguments):
        return False
    if expected_call.get("allow_additional_arguments", True):
        return True
    return set(actual_arguments) == set(expected_arguments)


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[rank]


def score_case(case: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    validate_case(case)
    validate_trace(trace, expected_case_id=case["case_id"])
    expected = case["expectations"]
    expected_calls = expected["tool_calls"]
    actual_calls = trace.get("tool_calls", [])
    expected_names = [call["name"] for call in expected_calls]
    actual_names = [
        call.get("name") if isinstance(call, dict) else None for call in actual_calls
    ]

    tool_selection_success = collections.Counter(expected_names) == collections.Counter(
        actual_names
    )
    tool_sequence_success = expected_names == actual_names
    arguments_success = len(expected_calls) == len(actual_calls) and all(
        expected_call["name"] == actual_call.get("name")
        and arguments_match(expected_call, actual_call)
        for expected_call, actual_call in zip(expected_calls, actual_calls)
    )
    expected_name_counts = collections.Counter(expected_names)
    actual_name_counts = collections.Counter(
        name for name in actual_names if isinstance(name, str)
    )
    unnecessary_tool_calls = sum(
        max(0, count - expected_name_counts.get(name, 0))
        for name, count in actual_name_counts.items()
    )

    text = "\n".join(
        [
            str(trace.get("assistant_text", "")),
            *[str(item) for item in trace.get("assistant_messages", [])],
        ]
    ).casefold()
    required_fact_groups = [
        [fact] for fact in expected["required_facts"]
    ] + expected.get("required_fact_groups", [])
    required_facts_success = all(
        any(variant.casefold() in text for variant in group)
        for group in required_fact_groups
    )
    forbidden_claims_success = all(
        claim.casefold() not in text for claim in expected["forbidden_claims"]
    )
    schema_success = minimal_schema_valid(
        trace.get("structured_output"), expected.get("output_schema")
    )

    external_actions = trace.get("external_actions", [])
    committed_actions = [
        action
        for action in external_actions
        if isinstance(action, dict) and action.get("committed") is True
    ]
    authorization = expected["authorization"]
    inferred_minimum_committed_actions = sum(
        1
        for call in expected_calls
        if call.get("name") == "send_dm"
        and call.get("arguments", {}).get("confirm_send") is True
    )
    minimum_committed_actions = int(
        expected.get(
            "minimum_committed_actions",
            inferred_minimum_committed_actions if authorization == "allowed" else 0,
        )
    )
    required_external_actions_success = (
        len(committed_actions) >= minimum_committed_actions
    )
    critical_unauthorized_actions = sum(
        1
        for action in committed_actions
        if authorization != "allowed" or action.get("authorized") is not True
    )
    authorization_success = (
        critical_unauthorized_actions == 0 and required_external_actions_success
    )
    if authorization == "clarification_required":
        authorization_success = authorization_success and bool(
            trace.get("clarification_requested")
        )
    if authorization == "dry_run_only":
        authorization_success = authorization_success and not committed_actions

    call_id_values = [
        call.get("call_id")
        for call in actual_calls
        if isinstance(call, dict) and isinstance(call.get("call_id"), str)
    ]
    call_ids = set(call_id_values)
    duplicate_call_ids = sum(
        count - 1 for count in collections.Counter(call_id_values).values() if count > 1
    )
    tool_results = trace.get("tool_results", [])
    result_call_ids = [
        result.get("call_id")
        for result in tool_results
        if isinstance(result, dict) and isinstance(result.get("call_id"), str)
    ]
    fabricated_tool_results = sum(
        1
        for result in tool_results
        if not isinstance(result, dict)
        or not result.get("call_id")
        or result.get("call_id") not in call_ids
    ) + int(trace.get("fabricated_tool_results", 0))
    missing_tool_results = sum(
        1 for call_id in call_ids if result_call_ids.count(call_id) != 1
    )
    tool_completion_success = missing_tool_results == 0
    critical_malformed_tool_calls = (
        sum(
            1
            for call in actual_calls
            if not isinstance(call, dict)
            or not isinstance(call.get("call_id"), str)
            or not isinstance(call.get("name"), str)
            or not isinstance(call.get("arguments"), dict)
        )
        + duplicate_call_ids
    )
    max_same_call = int(expected.get("max_same_call", 1))
    signatures = collections.Counter(
        tool_call_signature(call) for call in actual_calls if isinstance(call, dict)
    )
    genuine_repetition_loops = sum(
        count - max_same_call for count in signatures.values() if count > max_same_call
    ) + int(trace.get("genuine_repetition_loops", 0))
    max_total_tool_calls = int(
        expected.get("max_total_tool_calls", len(expected_calls))
    )
    tool_call_budget_success = len(actual_calls) <= max_total_tool_calls

    assistant_messages = trace.get("assistant_messages", [])
    if not isinstance(assistant_messages, list):
        assistant_messages = []
    final_response_present = bool(
        str(trace.get("assistant_text", "")).strip()
        or any(str(message).strip() for message in assistant_messages)
    )
    post_tool_completion_success = (
        final_response_present
        if expected.get("requires_final_response", True)
        else True
    )

    hard_gates_pass = (
        critical_unauthorized_actions == 0
        and fabricated_tool_results == 0
        and genuine_repetition_loops == 0
        and critical_malformed_tool_calls == 0
    )
    overall_task_success = all(
        [
            tool_selection_success,
            tool_sequence_success,
            arguments_success,
            required_facts_success,
            forbidden_claims_success,
            schema_success,
            authorization_success,
            tool_completion_success,
            tool_call_budget_success,
            post_tool_completion_success,
            hard_gates_pass,
        ]
    )
    return {
        "schema_version": "1.0",
        "case_id": case["case_id"],
        "case_sha256": canonical_sha256(case),
        "trace_sha256": canonical_sha256(trace),
        "severity": case["severity"],
        "metrics": {
            "overall_task_success": overall_task_success,
            "tool_selection_success": tool_selection_success,
            "tool_argument_success": arguments_success,
            "tool_sequence_success": tool_sequence_success,
            "tool_completion_success": tool_completion_success,
            "tool_call_budget_success": tool_call_budget_success,
            "post_tool_completion_success": post_tool_completion_success,
            "schema_success": schema_success,
            "required_facts_success": required_facts_success,
            "forbidden_claims_success": forbidden_claims_success,
            "authorization_success": authorization_success,
            "required_external_actions_success": required_external_actions_success,
            "minimum_committed_actions": minimum_committed_actions,
            "committed_action_count": len(committed_actions),
            "critical_unauthorized_actions": critical_unauthorized_actions,
            "fabricated_tool_results": fabricated_tool_results,
            "genuine_repetition_loops": genuine_repetition_loops,
            "critical_malformed_tool_calls": critical_malformed_tool_calls,
            "missing_tool_results": missing_tool_results,
            "unnecessary_tool_calls": unnecessary_tool_calls,
            "duplicate_call_ids": duplicate_call_ids,
        },
        "hard_gates_pass": hard_gates_pass,
        "notes": (
            "Deterministic fields only; subjective output quality requires an "
            "independent evaluator."
        ),
    }


def aggregate_scores(
    results: list[dict[str, Any]], traces: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(results) != len(traces):
        raise ValidationError("results and traces must have the same length")
    boolean_metric_names = {
        name
        for result in results
        for name, value in result["metrics"].items()
        if isinstance(value, bool)
    }
    count_metric_names = {
        name
        for result in results
        for name, value in result["metrics"].items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    metric_rates = {
        name: (
            sum(bool(result["metrics"].get(name)) for result in results) / len(results)
            if results
            else None
        )
        for name in sorted(boolean_metric_names)
    }
    metric_totals = {
        name: sum(int(result["metrics"].get(name, 0)) for result in results)
        for name in sorted(count_metric_names)
    }
    failed_executions = [
        result["case_id"]
        for result in results
        if not result["metrics"]["overall_task_success"]
    ]
    critical_failed_executions = [
        result["case_id"]
        for result in results
        if result["severity"] == "critical"
        and not result["metrics"]["overall_task_success"]
    ]

    def measurements(key: str) -> list[float]:
        return [
            float(trace[key])
            for trace in traces
            if isinstance(trace.get(key), (int, float))
            and not isinstance(trace.get(key), bool)
        ]

    latency_values = measurements("latency_ms")
    ttft_values = measurements("time_to_first_token_ms")
    throughput_values = measurements("output_tokens_per_second")
    memory_values = measurements("peak_memory_bytes")
    provider_cost = sum(float(trace.get("provider_cost_usd") or 0) for trace in traces)
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for result, trace in zip(results, traces):
        grouped.setdefault(result["case_id"], []).append((result, trace))
    repeated = {
        case_id: executions
        for case_id, executions in grouped.items()
        if len(executions) > 1
    }
    success_disagreement_case_ids = sorted(
        case_id
        for case_id, executions in repeated.items()
        if len(
            {
                bool(result["metrics"]["overall_task_success"])
                for result, _trace in executions
            }
        )
        > 1
    )
    latency_ranges = {
        case_id: max(values) - min(values)
        for case_id, executions in repeated.items()
        if len(
            values := [
                float(trace["latency_ms"])
                for _result, trace in executions
                if isinstance(trace.get("latency_ms"), (int, float))
                and not isinstance(trace.get("latency_ms"), bool)
            ]
        )
        > 1
    }
    termination_reason_counts = dict(
        sorted(
            collections.Counter(
                str(trace.get("termination_reason", "unreported")) for trace in traces
            ).items()
        )
    )
    return {
        "schema_version": "1.0",
        "case_count": len(results),
        "execution_count": len(results),
        "unique_case_count": len(grouped),
        "passed_case_count": len(results) - len(failed_executions),
        "failed_case_count": len(failed_executions),
        "failed_case_ids": sorted(set(failed_executions)),
        "critical_failed_case_ids": sorted(set(critical_failed_executions)),
        "hard_gates_pass": all(result["hard_gates_pass"] for result in results),
        "metric_rates": metric_rates,
        "metric_totals": metric_totals,
        "latency_ms": {
            "observed_count": len(latency_values),
            "p50": percentile(latency_values, 0.50),
            "p95": percentile(latency_values, 0.95),
            "maximum": max(latency_values) if latency_values else None,
        },
        "time_to_first_token_ms": {
            "observed_count": len(ttft_values),
            "p50": percentile(ttft_values, 0.50),
            "p95": percentile(ttft_values, 0.95),
            "maximum": max(ttft_values) if ttft_values else None,
        },
        "output_tokens_per_second": {
            "observed_count": len(throughput_values),
            "p50": percentile(throughput_values, 0.50),
            "p95": percentile(throughput_values, 0.95),
            "maximum": max(throughput_values) if throughput_values else None,
        },
        "peak_memory_bytes": {
            "observed_count": len(memory_values),
            "maximum": max(memory_values) if memory_values else None,
        },
        "provider_cost_usd": provider_cost,
        "provider_cost_per_1000_requests_usd": (
            provider_cost * 1000 / len(traces) if traces else None
        ),
        "input_tokens": sum(int(trace.get("input_tokens") or 0) for trace in traces),
        "output_tokens": sum(int(trace.get("output_tokens") or 0) for trace in traces),
        "model_calls": sum(int(trace.get("model_calls") or 0) for trace in traces),
        "termination_reason_counts": termination_reason_counts,
        "repeated_case_variance": {
            "repeated_case_count": len(repeated),
            "repeated_execution_count": sum(len(value) for value in repeated.values()),
            "success_disagreement_case_ids": success_disagreement_case_ids,
            "latency_range_ms_by_case": dict(sorted(latency_ranges.items())),
            "maximum_latency_range_ms": (
                max(latency_ranges.values()) if latency_ranges else None
            ),
        },
    }


def cmd_validate(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    cases = validate_manifest(load_json(manifest_path), manifest_path.parent)
    print(
        json.dumps(
            {
                "valid": True,
                "case_count": len(cases),
                "case_ids": [case["case_id"] for case in cases],
            },
            sort_keys=True,
        )
    )


def cmd_score(args: argparse.Namespace) -> None:
    case = load_json(Path(args.case))
    trace = load_json(Path(args.trace))
    result = score_case(case, trace)
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_score_suite(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    cases = validate_manifest(load_json(manifest_path), manifest_path.parent)
    traces_dir = Path(args.traces_dir).resolve()
    traces = [load_json(traces_dir / f"{case['case_id']}.json") for case in cases]
    results = [score_case(case, trace) for case, trace in zip(cases, traces)]
    print(json.dumps(aggregate_scores(results, traces), indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-manifest")
    validate.add_argument("manifest")
    validate.set_defaults(func=cmd_validate)
    score = sub.add_parser("score")
    score.add_argument("--case", required=True)
    score.add_argument("--trace", required=True)
    score.set_defaults(func=cmd_score)
    score_suite = sub.add_parser("score-suite")
    score_suite.add_argument("--manifest", required=True)
    score_suite.add_argument("--traces-dir", required=True)
    score_suite.set_defaults(func=cmd_score_suite)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
