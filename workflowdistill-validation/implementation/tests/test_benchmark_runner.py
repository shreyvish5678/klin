import json
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_eval import canonical_sha256
from tools.benchmark_runner import (
    SuitePolicy,
    VisibleBenchmarkRunner,
    fixture_executor_factory,
    tool_specs_from_surface,
    write_suite_artifacts,
)
from tools.model_harness import (
    AuthorizationContext,
    ModelRequest,
    ModelTurn,
    ToolCall,
    ToolSpec,
)


TOOLS = [
    ToolSpec("discord_identity", "Synthetic identity.", {"type": "object"}),
    ToolSpec(
        "send_dm",
        "Synthetic send.",
        {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "content": {"type": "string"},
                "confirm_send": {"type": "boolean"},
                "confirmation_token": {"type": ["string", "null"]},
            },
        },
    ),
]


def benchmark_case(
    case_id,
    *,
    split,
    user_message,
    tools,
    expected_calls,
    required_facts,
    fixtures=None,
    history=None,
    authorization="allowed",
    private=False,
):
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "split": split,
        "task_category": "synthetic runner plumbing",
        "severity": "critical" if "send" in case_id else "noncritical",
        "input": {"user_message": user_message},
        "context": {
            "contains_private_data": private,
            "conversation_history": history or [],
            "tool_fixtures": fixtures or [],
        },
        "tools": [{"name": name} for name in tools],
        "expectations": {
            "tool_calls": expected_calls,
            "required_facts": required_facts,
            "required_fact_groups": [],
            "forbidden_claims": [],
            "authorization": authorization,
            "output_schema": None,
            "max_same_call": 1,
            "max_total_tool_calls": len(expected_calls),
            "minimum_committed_actions": (
                sum(
                    call["name"] == "send_dm"
                    and call["arguments"].get("confirm_send") is True
                    for call in expected_calls
                )
                if authorization == "allowed"
                else 0
            ),
            "requires_final_response": True,
        },
        "source": {"kind": "synthetic", "evidence_paths": ["unit-test"]},
        "privacy": {
            "contains_private_data": private,
            "external_use_approved": False,
        },
    }


def cases():
    direct = benchmark_case(
        "synthetic-direct",
        split="development",
        user_message="Answer directly.",
        tools=["discord_identity"],
        expected_calls=[],
        required_facts=["direct"],
        history=[
            {"role": "user", "content": "Synthetic prior context."},
            {"role": "assistant", "content": "Synthetic prior response."},
        ],
    )
    identity = benchmark_case(
        "synthetic-identity",
        split="selection",
        user_message="Inspect identity.",
        tools=["discord_identity"],
        expected_calls=[
            {
                "name": "discord_identity",
                "arguments": {},
                "allow_additional_arguments": False,
            }
        ],
        required_facts=["available"],
        fixtures=[
            {
                "tool": "discord_identity",
                "result": {"user_id": "900", "username": "demo"},
            }
        ],
    )
    send = benchmark_case(
        "synthetic-send",
        split="selection",
        user_message="Send exact synthetic text.",
        tools=["send_dm"],
        expected_calls=[
            {
                "name": "send_dm",
                "arguments": {
                    "channel_id": "111",
                    "content": "hello",
                    "confirm_send": False,
                },
                "allow_additional_arguments": False,
            },
            {
                "name": "send_dm",
                "arguments": {
                    "channel_id": "111",
                    "content": "hello",
                    "confirm_send": True,
                    "confirmation_token": "synthetic-receipt",
                },
                "allow_additional_arguments": False,
            },
        ],
        required_facts=["sent"],
        fixtures=[
            {
                "tool": "send_dm",
                "result": {
                    "sent": False,
                    "dry_run": True,
                    "confirmation_token": "synthetic-receipt",
                },
            },
            {
                "tool": "send_dm",
                "result": {"sent": True, "message_id": "777"},
            },
        ],
    )
    return [direct, identity, send]


class ScriptedBackend:
    backend_id = "fake-suite"
    model_id = "scripted-suite"

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests: list[ModelRequest] = []

    async def complete(self, request):
        self.requests.append(request)
        return self.turns.pop(0)


class ScriptedBackendFactory:
    def __init__(self):
        self.backends = []

    def __call__(self, case, repetition):
        if case["case_id"] == "synthetic-direct":
            turns = [ModelTurn(assistant_text="A direct synthetic answer.")]
        elif case["case_id"] == "synthetic-identity":
            turns = [
                ModelTurn(tool_calls=(ToolCall("call-1", "discord_identity", {}),)),
                ModelTurn(assistant_text="Synthetic identity is available."),
            ]
        else:
            turns = [
                ModelTurn(
                    tool_calls=(
                        ToolCall(
                            "call-1",
                            "send_dm",
                            {
                                "channel_id": "111",
                                "content": "hello",
                                "confirm_send": False,
                            },
                        ),
                    )
                ),
                ModelTurn(
                    tool_calls=(
                        ToolCall(
                            "call-2",
                            "send_dm",
                            {
                                "channel_id": "111",
                                "content": "hello",
                                "confirm_send": True,
                                "confirmation_token": "synthetic-receipt",
                            },
                        ),
                    )
                ),
                ModelTurn(assistant_text="Synthetic message sent."),
            ]
        backend = ScriptedBackend(turns)
        self.backends.append((case["case_id"], repetition, backend))
        return backend


def authorization_factory(case, _repetition):
    if case["case_id"] != "synthetic-send":
        return None
    return AuthorizationContext(
        allow_send_commit=True,
        channel_id="111",
        content="hello",
    )


def write_manifest(root, benchmark_cases):
    records = []
    for case in benchmark_cases:
        path = root / f"{case['case_id']}.json"
        path.write_text(json.dumps(case), encoding="utf-8")
        records.append(
            {
                "case_id": case["case_id"],
                "path": path.name,
                "split": case["split"],
                "sha256": canonical_sha256(case),
            }
        )
    records.append(
        {
            "case_id": "protected-hidden",
            "path": "protected-hidden-does-not-exist.json",
            "split": "hidden",
            "sha256": "0" * 64,
        }
    )
    manifest = {
        "schema_version": "1.0",
        "status": "DRAFT_NOT_FROZEN",
        "sha256": None,
        "cases": records,
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def runner(factory, **policy_overrides):
    policy = SuitePolicy(
        allowed_splits=frozenset({"development", "selection"}),
        require_frozen_manifest=False,
        repetitions=2,
        run_classification="PREPARATION_FAKE_ONLY",
        execution_boundary="fake",
        **policy_overrides,
    )
    return VisibleBenchmarkRunner(
        suite_id="fake-suite-smoke",
        run_id="synthetic-run",
        source_revision="synthetic-revision",
        system_prompt="Synthetic immutable instructions.",
        tool_specs=TOOLS,
        backend_factory=factory,
        tool_executor_factory=fixture_executor_factory,
        authorization_factory=authorization_factory,
        policy=policy,
    )


class BenchmarkRunnerTests(unittest.IsolatedAsyncioTestCase):
    def test_source_tool_surface_preserves_required_fields_and_constraints(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "research"
            / "workflowdistill-discord-validation"
            / "benchmarks"
        )
        specs = {
            spec.name: spec
            for spec in tool_specs_from_surface(root / "draft-tool-surface.json")
        }
        self.assertEqual(
            specs["send_dm"].input_schema["required"],
            ["channel_id", "content"],
        )
        self.assertFalse(specs["send_dm"].input_schema["additionalProperties"])
        self.assertIn(
            "matching unexpired one-time receipt", specs["send_dm"].description
        )
        self.assertEqual(specs["web_search"].input_schema["required"], ["query"])

    async def test_visible_suite_runs_repeats_scores_and_writes_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = write_manifest(root, cases())
            factory = ScriptedBackendFactory()
            result = await runner(factory).run(manifest_path)

            self.assertEqual(result.summary["execution_count"], 6)
            self.assertEqual(result.summary["unique_case_count"], 3)
            self.assertEqual(result.summary["passed_case_count"], 6)
            self.assertTrue(result.summary["hard_gates_pass"])
            self.assertEqual(
                result.summary["repeated_case_variance"]["repeated_case_count"],
                3,
            )
            self.assertFalse(result.provenance["official_evaluation"])
            self.assertFalse(result.provenance["hidden_labels_loaded"])
            self.assertFalse(result.provenance["private_cases_loaded"])
            self.assertFalse(result.provenance["private_evaluation_traces_persisted"])
            self.assertEqual(result.provenance["execution_count"], 6)

            direct_trace = result.traces["synthetic-direct--r01"]
            self.assertEqual(direct_trace["context_message_count"], 2)
            self.assertNotIn("Synthetic prior context.", str(direct_trace))
            send_trace = result.traces["synthetic-send--r01"]
            self.assertEqual(
                send_trace["tool_calls"][1]["arguments"]["confirmation_token"],
                "<redacted_secret>",
            )
            self.assertTrue(
                result.scores["synthetic-send--r01"]["metrics"][
                    "required_external_actions_success"
                ]
            )
            self.assertEqual(
                result.scores["synthetic-send--r01"]["trace_sha256"],
                canonical_sha256(send_trace),
            )
            self.assertTrue(send_trace["external_actions"][1]["authorized"])
            self.assertEqual(
                send_trace["external_actions"][1]["execution_boundary"],
                "fake",
            )

            output = root / "published-suite"
            write_suite_artifacts(output, result)
            self.assertTrue((output / "summary.json").is_file())
            self.assertTrue((output / "provenance.json").is_file())
            self.assertEqual(len(list((output / "traces").glob("*.json"))), 6)
            self.assertEqual(len(list((output / "scores").glob("*.json"))), 6)
            with self.assertRaises(FileExistsError):
                write_suite_artifacts(output, result)

    async def test_official_runner_refuses_unfrozen_manifest_before_backend_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = write_manifest(root, cases())
            factory = ScriptedBackendFactory()
            official = VisibleBenchmarkRunner(
                suite_id="official-suite",
                run_id="synthetic-run",
                source_revision="synthetic-revision",
                system_prompt="Synthetic immutable instructions.",
                tool_specs=TOOLS,
                backend_factory=factory,
                tool_executor_factory=fixture_executor_factory,
                contract_sha256="a" * 64,
                research_started_at="2026-07-17T00:00:00Z",
            )
            with self.assertRaisesRegex(ValueError, "requires FROZEN"):
                await official.run(manifest_path)
            self.assertEqual(factory.backends, [])

    async def test_visible_runner_rejects_private_case_before_backend_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_case = benchmark_case(
                "private-case",
                split="development",
                user_message="Private input.",
                tools=["discord_identity"],
                expected_calls=[],
                required_facts=[],
                private=True,
            )
            manifest_path = write_manifest(root, [private_case])
            factory = ScriptedBackendFactory()
            with self.assertRaisesRegex(ValueError, "refuses private case"):
                await runner(factory).run(manifest_path)
            self.assertEqual(factory.backends, [])

    def test_policy_rejects_hidden_and_fake_official_combinations(self):
        with self.assertRaisesRegex(ValueError, "allowed_splits"):
            SuitePolicy(allowed_splits=frozenset({"hidden"}))
        with self.assertRaisesRegex(ValueError, "fake execution"):
            SuitePolicy(execution_boundary="fake")

    async def test_official_runner_requires_contract_and_timer_before_backend_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = write_manifest(root, cases())
            factory = ScriptedBackendFactory()
            official = VisibleBenchmarkRunner(
                suite_id="official-suite",
                run_id="synthetic-run",
                source_revision="synthetic-revision",
                system_prompt="Synthetic immutable instructions.",
                tool_specs=TOOLS,
                backend_factory=factory,
                tool_executor_factory=fixture_executor_factory,
            )
            with self.assertRaisesRegex(ValueError, "frozen contract hash"):
                await official.run(manifest_path)
            contract_only = VisibleBenchmarkRunner(
                suite_id="official-suite",
                run_id="synthetic-run",
                source_revision="synthetic-revision",
                system_prompt="Synthetic immutable instructions.",
                tool_specs=TOOLS,
                backend_factory=factory,
                tool_executor_factory=fixture_executor_factory,
                contract_sha256="a" * 64,
            )
            with self.assertRaisesRegex(ValueError, "active research timer"):
                await contract_only.run(manifest_path)
            self.assertEqual(factory.backends, [])


if __name__ == "__main__":
    unittest.main()
