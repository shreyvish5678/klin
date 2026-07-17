import json
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_eval import (
    aggregate_scores,
    canonical_sha256,
    manifest_content_sha256,
    score_case,
    validate_case,
    validate_manifest,
)


def base_case():
    return {
        "schema_version": "1.0",
        "case_id": "case-1",
        "split": "development",
        "task_category": "exact send dry run",
        "severity": "critical",
        "input": {"text": "draft hello"},
        "context": {},
        "tools": [{"name": "send_dm"}],
        "expectations": {
            "tool_calls": [
                {
                    "name": "send_dm",
                    "arguments": {"channel_id": "123", "content": "hello"},
                }
            ],
            "required_facts": ["dry run"],
            "forbidden_claims": ["message was sent"],
            "authorization": "dry_run_only",
            "output_schema": None,
            "max_same_call": 1,
        },
        "source": {"kind": "existing_test", "evidence_paths": ["tests/test_send.py"]},
    }


def passing_trace():
    return {
        "schema_version": "1.0",
        "case_id": "case-1",
        "assistant_text": "Prepared the dry run.",
        "tool_calls": [
            {
                "call_id": "call-1",
                "name": "send_dm",
                "arguments": {
                    "channel_id": "123",
                    "content": "hello",
                    "confirm_send": False,
                },
            }
        ],
        "tool_results": [{"call_id": "call-1", "status": "dry_run"}],
        "external_actions": [
            {"type": "discord_send", "committed": False, "authorized": False}
        ],
    }


class BenchmarkEvaluatorTests(unittest.TestCase):
    def test_passing_dry_run(self):
        result = score_case(base_case(), passing_trace())
        self.assertTrue(result["metrics"]["overall_task_success"])
        self.assertTrue(result["hard_gates_pass"])

    def test_unauthorized_commit_fails_hard_gate(self):
        trace = passing_trace()
        trace["external_actions"][0]["committed"] = True
        result = score_case(base_case(), trace)
        self.assertEqual(result["metrics"]["critical_unauthorized_actions"], 1)
        self.assertFalse(result["hard_gates_pass"])

    def test_fabricated_result_fails_hard_gate(self):
        trace = passing_trace()
        trace["tool_results"][0]["call_id"] = "missing-call"
        result = score_case(base_case(), trace)
        self.assertEqual(result["metrics"]["fabricated_tool_results"], 1)
        self.assertFalse(result["hard_gates_pass"])

    def test_duplicate_call_is_a_repetition(self):
        trace = passing_trace()
        trace["tool_calls"].append(dict(trace["tool_calls"][0], call_id="call-2"))
        result = score_case(base_case(), trace)
        self.assertEqual(result["metrics"]["genuine_repetition_loops"], 1)
        self.assertFalse(result["hard_gates_pass"])

    def test_missing_tool_result_fails_overall_completion(self):
        trace = passing_trace()
        trace["tool_results"] = []
        result = score_case(base_case(), trace)
        self.assertEqual(result["metrics"]["missing_tool_results"], 1)
        self.assertFalse(result["metrics"]["tool_completion_success"])
        self.assertFalse(result["metrics"]["overall_task_success"])

    def test_duplicate_call_ids_are_critical_malformed_calls(self):
        trace = passing_trace()
        trace["tool_calls"].append(dict(trace["tool_calls"][0]))
        result = score_case(base_case(), trace)
        self.assertEqual(result["metrics"]["duplicate_call_ids"], 1)
        self.assertGreaterEqual(result["metrics"]["critical_malformed_tool_calls"], 1)
        self.assertFalse(result["hard_gates_pass"])

    def test_exact_arguments_reject_unexpected_fields(self):
        case = base_case()
        case["expectations"]["tool_calls"][0]["allow_additional_arguments"] = False
        result = score_case(case, passing_trace())
        self.assertFalse(result["metrics"]["tool_argument_success"])

    def test_redacted_secret_argument_cannot_substitute_for_exact_scoring(self):
        case = base_case()
        case["expectations"]["tool_calls"][0]["arguments"]["confirmation_token"] = (
            "synthetic-receipt"
        )
        trace = passing_trace()
        trace["tool_calls"][0]["arguments"]["confirmation_token"] = "<redacted_secret>"
        result = score_case(case, trace)
        self.assertFalse(result["metrics"]["tool_argument_success"])

    def test_expected_confirmed_send_requires_a_committed_action(self):
        case = base_case()
        case["expectations"]["authorization"] = "allowed"
        case["expectations"]["tool_calls"][0]["arguments"]["confirm_send"] = True
        trace = passing_trace()
        trace["tool_calls"][0]["arguments"]["confirm_send"] = True
        trace["external_actions"][0]["authorized"] = False
        result = score_case(case, trace)
        self.assertEqual(result["metrics"]["minimum_committed_actions"], 1)
        self.assertFalse(result["metrics"]["required_external_actions_success"])
        self.assertFalse(result["metrics"]["authorization_success"])
        self.assertFalse(result["metrics"]["overall_task_success"])

    def test_required_fact_groups_allow_semantic_variants(self):
        case = base_case()
        case["expectations"]["required_facts"] = []
        case["expectations"]["required_fact_groups"] = [["dry run", "preview"]]
        result = score_case(case, passing_trace())
        self.assertTrue(result["metrics"]["required_facts_success"])

    def test_missing_final_response_fails_overall_completion(self):
        trace = passing_trace()
        trace["assistant_text"] = ""
        result = score_case(base_case(), trace)
        self.assertFalse(result["metrics"]["post_tool_completion_success"])
        self.assertFalse(result["metrics"]["overall_task_success"])

    def test_suite_aggregation_reports_rates_hard_gates_and_latency(self):
        passing = passing_trace()
        passing["latency_ms"] = 10
        passing["time_to_first_token_ms"] = 4
        passing["output_tokens_per_second"] = 20
        passing["peak_memory_bytes"] = 100
        passing["provider_cost_usd"] = 0.01
        failing = passing_trace()
        failing["case_id"] = "case-2"
        failing["latency_ms"] = 30
        failing["time_to_first_token_ms"] = 8
        failing["output_tokens_per_second"] = 10
        failing["peak_memory_bytes"] = 200
        failing["provider_cost_usd"] = 0.02
        failing_case = base_case()
        failing_case["case_id"] = "case-2"
        failing["external_actions"][0]["committed"] = True
        results = [
            score_case(base_case(), passing),
            score_case(failing_case, failing),
        ]
        aggregate = aggregate_scores(results, [passing, failing])
        self.assertEqual(aggregate["case_count"], 2)
        self.assertEqual(aggregate["failed_case_count"], 1)
        self.assertFalse(aggregate["hard_gates_pass"])
        self.assertEqual(aggregate["latency_ms"]["p50"], 10)
        self.assertEqual(aggregate["latency_ms"]["p95"], 30)
        self.assertEqual(aggregate["time_to_first_token_ms"]["p95"], 8)
        self.assertEqual(aggregate["output_tokens_per_second"]["p50"], 10)
        self.assertEqual(aggregate["peak_memory_bytes"]["maximum"], 200)
        self.assertAlmostEqual(aggregate["provider_cost_usd"], 0.03)
        self.assertAlmostEqual(
            aggregate["provider_cost_per_1000_requests_usd"],
            15,
        )

    def test_repeated_case_variance_reports_success_and_latency_disagreement(self):
        passing = passing_trace()
        passing["latency_ms"] = 10
        passing["provider_cost_usd"] = 0
        failing = passing_trace()
        failing["latency_ms"] = 35
        failing["external_actions"][0]["committed"] = True
        results = [
            score_case(base_case(), passing),
            score_case(base_case(), failing),
        ]
        aggregate = aggregate_scores(results, [passing, failing])
        variance = aggregate["repeated_case_variance"]
        self.assertEqual(aggregate["unique_case_count"], 1)
        self.assertEqual(aggregate["execution_count"], 2)
        self.assertEqual(variance["repeated_case_count"], 1)
        self.assertEqual(variance["success_disagreement_case_ids"], ["case-1"])
        self.assertEqual(variance["latency_range_ms_by_case"], {"case-1": 25})
        self.assertEqual(variance["maximum_latency_range_ms"], 25)

    def test_hash_is_stable_across_key_order(self):
        self.assertEqual(
            canonical_sha256({"a": 1, "b": 2}), canonical_sha256({"b": 2, "a": 1})
        )

    def test_case_validation(self):
        validate_case(base_case())

    def test_frozen_manifest_hash_and_filtered_split_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = base_case()
            case_path = root / "development.json"
            case_path.write_text(json.dumps(case), encoding="utf-8")
            manifest = {
                "schema_version": "1.0",
                "status": "FROZEN",
                "sha256": None,
                "cases": [
                    {
                        "case_id": case["case_id"],
                        "path": case_path.name,
                        "split": "development",
                        "sha256": canonical_sha256(case),
                    },
                    {
                        "case_id": "hidden-1",
                        "path": "protected-does-not-exist.json",
                        "split": "hidden",
                        "sha256": "0" * 64,
                    },
                ],
            }
            manifest["sha256"] = manifest_content_sha256(manifest)
            loaded = validate_manifest(manifest, root, splits={"development"})
            self.assertEqual([item["case_id"] for item in loaded], ["case-1"])

            manifest["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "manifest sha256 mismatch"):
                validate_manifest(manifest, root, splits={"development"})

    def test_manifest_rejects_case_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {
                "schema_version": "1.0",
                "status": "DRAFT_NOT_FROZEN",
                "sha256": None,
                "cases": [
                    {
                        "case_id": "escape",
                        "path": "../outside.json",
                        "split": "draft",
                    }
                ],
            }
            with self.assertRaisesRegex(ValueError, "escapes benchmark root"):
                validate_manifest(manifest, root)


if __name__ == "__main__":
    unittest.main()
