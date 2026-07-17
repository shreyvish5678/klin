#!/usr/bin/env python3
"""Model-neutral visible-suite execution with normalized traces and provenance."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

try:
    from benchmark_eval import (
        ValidationError,
        aggregate_scores,
        canonical_sha256,
        load_json,
        manifest_content_sha256,
        score_case,
        validate_manifest,
    )
    from model_harness import (
        AgentHarness,
        AuthorizationContext,
        ModelBackend,
        SafeToolError,
        ToolExecutor,
        ToolSpec,
        TracePolicy,
    )
except ModuleNotFoundError:
    from tools.benchmark_eval import (
        ValidationError,
        aggregate_scores,
        canonical_sha256,
        load_json,
        manifest_content_sha256,
        score_case,
        validate_manifest,
    )
    from tools.model_harness import (
        AgentHarness,
        AuthorizationContext,
        ModelBackend,
        SafeToolError,
        ToolExecutor,
        ToolSpec,
        TracePolicy,
    )


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "research" / "workflowdistill-discord-validation"
EVALUATOR_PATH = ROOT / "tools" / "benchmark_eval.py"
HARNESS_PATH = ROOT / "tools" / "model_harness.py"
RUNNER_PATH = ROOT / "tools" / "benchmark_runner.py"
TRACE_SCHEMA_PATH = RUN_DIR / "benchmarks" / "trace.schema.json"
CASE_SCHEMA_PATH = RUN_DIR / "benchmarks" / "case.schema.json"
VISIBLE_SPLITS = frozenset({"draft", "development", "selection"})
RUN_CLASSIFICATIONS = frozenset(
    {
        "PREPARATION_FAKE_ONLY",
        "REGRESSION_VISIBLE_ONLY",
        "OFFICIAL_VISIBLE_EVALUATION",
    }
)
EXECUTION_BOUNDARIES = frozenset(
    {"fake", "local", "external_hosted", "sandbox_discord"}
)
ARTIFACT_ID = re.compile(r"^[A-Za-z0-9._-]+$")

BackendFactory = Callable[[dict[str, Any], int], ModelBackend]
ToolExecutorFactory = Callable[[dict[str, Any], int], ToolExecutor]
AuthorizationFactory = Callable[
    [dict[str, Any], int],
    AuthorizationContext | None,
]


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@dataclass(frozen=True)
class SuitePolicy:
    allowed_splits: frozenset[str] = frozenset({"development", "selection"})
    require_frozen_manifest: bool = True
    repetitions: int = 1
    run_classification: str = "OFFICIAL_VISIBLE_EVALUATION"
    execution_boundary: str = "local"

    def __post_init__(self) -> None:
        if not self.allowed_splits or not self.allowed_splits <= VISIBLE_SPLITS:
            raise ValueError(
                "allowed_splits must contain only draft, development, or selection"
            )
        if self.repetitions < 1 or self.repetitions > 20:
            raise ValueError("repetitions must be between 1 and 20")
        if self.run_classification not in RUN_CLASSIFICATIONS:
            raise ValueError("unsupported run_classification")
        if self.execution_boundary not in EXECUTION_BOUNDARIES:
            raise ValueError("unsupported execution_boundary")
        if (
            self.run_classification == "OFFICIAL_VISIBLE_EVALUATION"
            and not self.require_frozen_manifest
        ):
            raise ValueError("official evaluation requires a frozen manifest")
        if (
            self.run_classification == "OFFICIAL_VISIBLE_EVALUATION"
            and self.execution_boundary == "fake"
        ):
            raise ValueError("fake execution cannot be an official evaluation")
        if (
            self.run_classification == "PREPARATION_FAKE_ONLY"
            and self.execution_boundary != "fake"
        ):
            raise ValueError("fake preparation must use the fake boundary")


@dataclass
class SuiteRunResult:
    summary: dict[str, Any]
    provenance: dict[str, Any]
    traces: dict[str, dict[str, Any]]
    scores: dict[str, dict[str, Any]]


class FixtureToolExecutor:
    """Sequential synthetic fixture executor; it never calls a real tool."""

    def __init__(self, fixtures: list[dict[str, Any]]) -> None:
        self.fixtures = copy.deepcopy(fixtures)
        self.position = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, copy.deepcopy(arguments)))
        if self.position >= len(self.fixtures):
            raise SafeToolError(f"no synthetic fixture is available for {name}")
        fixture = self.fixtures[self.position]
        if fixture.get("tool") != name:
            raise SafeToolError(
                f"synthetic fixture expected {fixture.get('tool')}, not {name}"
            )
        self.position += 1
        if "safe_error" in fixture:
            raise SafeToolError(str(fixture["safe_error"]))
        if "result" not in fixture:
            raise SafeToolError(f"synthetic fixture for {name} has no result")
        return copy.deepcopy(fixture["result"])


def fixture_executor_factory(
    case: dict[str, Any],
    _repetition: int,
) -> FixtureToolExecutor:
    fixtures = case.get("context", {}).get("tool_fixtures", [])
    if not isinstance(fixtures, list):
        raise ValidationError("context.tool_fixtures must be a list")
    return FixtureToolExecutor(fixtures)


def tool_specs_from_surface(path: Path) -> list[ToolSpec]:
    surface = load_json(path)
    if not isinstance(surface, dict) or not isinstance(surface.get("tools"), list):
        raise ValidationError("tool surface must contain a tools list")
    specs = []
    for record in surface["tools"]:
        if not isinstance(record, dict):
            raise ValidationError("tool surface records must be objects")
        arguments = record.get("arguments")
        required = record.get("required", [])
        constraints = record.get("constraints", [])
        if (
            not isinstance(record.get("name"), str)
            or not record["name"]
            or not isinstance(record.get("description"), str)
            or not record["description"].strip()
            or not isinstance(arguments, dict)
            or not isinstance(required, list)
            or not all(isinstance(name, str) and name for name in required)
            or len(required) != len(set(required))
            or not set(required) <= set(arguments)
            or not isinstance(constraints, list)
            or not all(
                isinstance(constraint, str) and constraint.strip()
                for constraint in constraints
            )
        ):
            raise ValidationError(
                "tool surface records require valid name, description, arguments, "
                "required fields, and constraints"
            )
        description = record["description"].strip()
        if constraints:
            description += " Constraints: " + "; ".join(constraints) + "."
        specs.append(
            ToolSpec(
                name=record["name"],
                description=description,
                input_schema={
                    "type": "object",
                    "properties": copy.deepcopy(arguments),
                    "required": copy.deepcopy(required),
                    "additionalProperties": False,
                },
            )
        )
    return specs


class VisibleBenchmarkRunner:
    """Execute visible, nonprivate cases without opening hidden case files."""

    def __init__(
        self,
        *,
        suite_id: str,
        run_id: str,
        source_revision: str,
        system_prompt: str,
        tool_specs: list[ToolSpec],
        backend_factory: BackendFactory,
        tool_executor_factory: ToolExecutorFactory,
        policy: SuitePolicy | None = None,
        authorization_factory: AuthorizationFactory | None = None,
        contract_sha256: str | None = None,
        research_started_at: str | None = None,
    ) -> None:
        for label, value in {
            "suite_id": suite_id,
            "run_id": run_id,
            "source_revision": source_revision,
        }.items():
            if not value.strip():
                raise ValueError(f"{label} must not be blank")
        if not ARTIFACT_ID.fullmatch(suite_id):
            raise ValueError("suite_id contains path-unsafe characters")
        if not system_prompt.strip():
            raise ValueError("system_prompt must not be blank")
        if contract_sha256 is not None and not re.fullmatch(
            r"[a-f0-9]{64}",
            contract_sha256,
        ):
            raise ValueError("contract_sha256 must be a lowercase SHA-256 digest")
        if research_started_at is not None and not research_started_at.strip():
            raise ValueError("research_started_at must be a nonempty timestamp")
        names = [spec.name for spec in tool_specs]
        if len(names) != len(set(names)):
            raise ValueError("tool_specs names must be unique")
        self.suite_id = suite_id
        self.run_id = run_id
        self.source_revision = source_revision
        self.system_prompt = system_prompt
        self.tool_specs = {spec.name: spec for spec in tool_specs}
        self.backend_factory = backend_factory
        self.tool_executor_factory = tool_executor_factory
        self.policy = policy or SuitePolicy()
        self.authorization_factory = authorization_factory
        self.contract_sha256 = contract_sha256
        self.research_started_at = research_started_at

    def _load_cases(
        self,
        manifest_path: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        manifest_path = manifest_path.resolve()
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict):
            raise ValidationError("benchmark manifest must be an object")
        if self.policy.run_classification == "OFFICIAL_VISIBLE_EVALUATION":
            if self.contract_sha256 is None:
                raise ValidationError(
                    "official visible evaluation requires a frozen contract hash"
                )
            if self.research_started_at is None:
                raise ValidationError(
                    "official visible evaluation requires an active research timer"
                )
        if self.policy.require_frozen_manifest and manifest.get("status") != "FROZEN":
            raise ValidationError(
                "official visible evaluation requires FROZEN manifest"
            )
        cases = validate_manifest(
            manifest,
            manifest_path.parent,
            splits=set(self.policy.allowed_splits),
        )
        if not cases:
            raise ValidationError("selected benchmark splits contain no cases")
        for case in cases:
            if case["split"] == "hidden":
                raise ValidationError("visible runner must never load hidden labels")
            contains_private_data = bool(
                case.get("privacy", {}).get("contains_private_data")
                or case.get("context", {}).get("contains_private_data")
            )
            if contains_private_data:
                raise ValidationError(
                    f"visible runner refuses private case {case['case_id']}"
                )
            if (
                not isinstance(case.get("input", {}).get("user_message"), str)
                or not case["input"]["user_message"].strip()
            ):
                raise ValidationError(
                    f"case {case['case_id']} requires input.user_message"
                )
            history = case.get("context", {}).get("conversation_history", [])
            if not isinstance(history, list):
                raise ValidationError(
                    f"case {case['case_id']} conversation_history must be a list"
                )
            case_tool_names = [record.get("name") for record in case["tools"]]
            if (
                any(not isinstance(name, str) or not name for name in case_tool_names)
                or len(case_tool_names) != len(set(case_tool_names))
                or any(name not in self.tool_specs for name in case_tool_names)
            ):
                raise ValidationError(
                    f"case {case['case_id']} has invalid or unknown tool declarations"
                )
        return manifest, cases

    async def run(self, manifest_path: Path) -> SuiteRunResult:
        started_at = utc_now()
        started = perf_counter()
        manifest, cases = self._load_cases(manifest_path)
        traces: dict[str, dict[str, Any]] = {}
        scores: dict[str, dict[str, Any]] = {}
        ordered_traces: list[dict[str, Any]] = []
        ordered_scores: list[dict[str, Any]] = []
        execution_records = []
        backend_identities: set[tuple[str, str]] = set()

        for repetition in range(1, self.policy.repetitions + 1):
            for case in cases:
                artifact_id = f"{case['case_id']}--r{repetition:02d}"
                if not ARTIFACT_ID.fullmatch(artifact_id):
                    raise ValidationError(
                        f"case_id cannot form a safe artifact name: {case['case_id']}"
                    )
                backend = self.backend_factory(case, repetition)
                if (
                    not isinstance(getattr(backend, "backend_id", None), str)
                    or not backend.backend_id
                    or not isinstance(getattr(backend, "model_id", None), str)
                    or not backend.model_id
                ):
                    raise ValidationError("backend identity must contain strings")
                backend_identities.add((backend.backend_id, backend.model_id))
                if len(backend_identities) > 1:
                    raise ValidationError(
                        "one suite run cannot mix backend or model identities"
                    )

                executor = self.tool_executor_factory(case, repetition)
                authorization = (
                    self.authorization_factory(case, repetition)
                    if self.authorization_factory is not None
                    else None
                )
                case_tools = [
                    self.tool_specs[record["name"]] for record in case["tools"]
                ]
                outcome = await AgentHarness(
                    backend=backend,
                    tool_executor=executor,
                    tools=case_tools,
                    system_prompt=self.system_prompt,
                    trace_policy=TracePolicy(retain_nonprivate_text=True),
                ).run(
                    case_id=case["case_id"],
                    user_message=case["input"]["user_message"],
                    conversation_history=case["context"].get(
                        "conversation_history",
                        [],
                    ),
                    authorization=authorization,
                )
                trace = copy.deepcopy(outcome.trace)
                trace["suite_repetition"] = repetition
                trace["execution_boundary"] = self.policy.execution_boundary
                trace["case_sha256"] = canonical_sha256(case)
                for action in trace.get("external_actions", []):
                    action["execution_boundary"] = self.policy.execution_boundary
                try:
                    score = score_case(case, outcome.private_evaluation_trace)
                finally:
                    outcome.private_evaluation_trace.clear()
                    outcome.private_runtime_messages.clear()
                # The private evaluation trace exists only in memory. Bind the
                # persisted score to the normalized trace without retaining a
                # digest derived from private runtime values.
                score["trace_sha256"] = canonical_sha256(trace)
                traces[artifact_id] = trace
                scores[artifact_id] = score
                ordered_traces.append(trace)
                ordered_scores.append(score)
                execution_records.append(
                    {
                        "artifact_id": artifact_id,
                        "case_id": case["case_id"],
                        "case_sha256": canonical_sha256(case),
                        "repetition": repetition,
                        "trace_sha256": canonical_sha256(trace),
                        "score_sha256": canonical_sha256(score),
                        "passed": score["metrics"]["overall_task_success"],
                    }
                )

        backend_id, model_id = next(iter(backend_identities))
        aggregate = aggregate_scores(ordered_scores, ordered_traces)
        aggregate.update(
            {
                "suite_id": self.suite_id,
                "run_id": self.run_id,
                "run_classification": self.policy.run_classification,
                "execution_boundary": self.policy.execution_boundary,
                "backend_id": backend_id,
                "model_id": model_id,
            }
        )
        provenance = {
            "schema_version": "1.0",
            "suite_id": self.suite_id,
            "run_id": self.run_id,
            "run_classification": self.policy.run_classification,
            "official_evaluation": (
                self.policy.run_classification == "OFFICIAL_VISIBLE_EVALUATION"
            ),
            "started_at": started_at,
            "completed_at": utc_now(),
            "elapsed_seconds": perf_counter() - started,
            "source_revision": self.source_revision,
            "contract_sha256": self.contract_sha256,
            "research_started_at": self.research_started_at,
            "manifest_status": manifest.get("status"),
            "manifest_sha256": manifest_content_sha256(manifest),
            "manifest_declared_sha256": manifest.get("sha256"),
            "selected_splits": sorted(self.policy.allowed_splits),
            "case_count": len(cases),
            "execution_count": len(execution_records),
            "repetitions": self.policy.repetitions,
            "backend_id": backend_id,
            "model_id": model_id,
            "system_prompt_sha256": hashlib.sha256(
                self.system_prompt.encode("utf-8")
            ).hexdigest(),
            "tool_specs_sha256": canonical_sha256(
                [spec.canonical() for spec in self.tool_specs.values()]
            ),
            "runner_source_sha256": file_sha256(RUNNER_PATH),
            "harness_source_sha256": file_sha256(HARNESS_PATH),
            "evaluator_source_sha256": file_sha256(EVALUATOR_PATH),
            "case_schema_sha256": file_sha256(CASE_SCHEMA_PATH),
            "trace_schema_sha256": file_sha256(TRACE_SCHEMA_PATH),
            "hidden_labels_loaded": False,
            "private_cases_loaded": False,
            "private_runtime_messages_persisted": False,
            "private_evaluation_traces_persisted": False,
            "private_runtime_state_cleared_after_scoring": True,
            "raw_tool_results_persisted": False,
            "execution_records": execution_records,
            "aggregate_sha256": canonical_sha256(aggregate),
        }
        return SuiteRunResult(
            summary=aggregate,
            provenance=provenance,
            traces=traces,
            scores=scores,
        )


def write_suite_artifacts(output_dir: Path, result: SuiteRunResult) -> None:
    """Atomically publish a new normalized suite directory without overwriting."""
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"suite output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.",
            dir=output_dir.parent,
        )
    )
    try:
        atomic_json(temporary / "summary.json", result.summary)
        atomic_json(temporary / "provenance.json", result.provenance)
        for artifact_id, trace in result.traces.items():
            atomic_json(temporary / "traces" / f"{artifact_id}.json", trace)
        for artifact_id, score in result.scores.items():
            atomic_json(temporary / "scores" / f"{artifact_id}.json", score)
        os.replace(temporary, output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
