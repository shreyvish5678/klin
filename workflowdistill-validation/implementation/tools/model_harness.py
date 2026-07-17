#!/usr/bin/env python3
"""Model-neutral orchestration for identical hosted and Bonsai agent paths."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol


SENSITIVE_KEY = re.compile(
    r"(authorization|api[-_]?key|password|secret|token|private[-_]?key)",
    re.IGNORECASE,
)


class SafeToolError(RuntimeError):
    """A tool failure whose message is safe to return to the model."""


class SafeModelError(RuntimeError):
    """A model-provider failure whose message is safe for the final response."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": copy.deepcopy(self.input_schema),
        }


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelRequest:
    system_prompt: str
    messages: tuple[dict[str, Any], ...]
    tools: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ModelTurn:
    assistant_text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    structured_output: Any | None = None
    clarification_requested: bool | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_cost_usd: float | None = None
    time_to_first_token_ms: float | None = None
    generation_seconds: float | None = None
    peak_memory_bytes: int | None = None


class ModelBackend(Protocol):
    backend_id: str
    model_id: str

    async def complete(self, request: ModelRequest) -> ModelTurn: ...


class ToolExecutor(Protocol):
    async def call(self, name: str, arguments: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class AuthorizationContext:
    allow_send_commit: bool = False
    channel_id: str | None = None
    content: str | None = None

    def authorizes(self, arguments: dict[str, Any]) -> bool:
        return (
            self.allow_send_commit
            and self.channel_id is not None
            and self.content is not None
            and arguments.get("channel_id") == self.channel_id
            and arguments.get("content") == self.content
        )


@dataclass(frozen=True)
class PendingSendConfirmation:
    channel_id: str
    content: str
    confirmation_token: str = field(repr=False)

    def matches(self, arguments: dict[str, Any]) -> bool:
        return (
            arguments.get("channel_id") == self.channel_id
            and arguments.get("content") == self.content
            and arguments.get("confirmation_token") == self.confirmation_token
        )


@dataclass(frozen=True)
class TracePolicy:
    retain_nonprivate_text: bool = False


@dataclass(frozen=True)
class HarnessConfig:
    maximum_model_turns: int = 8
    maximum_tool_calls: int = 12

    def __post_init__(self) -> None:
        if self.maximum_model_turns < 1:
            raise ValueError("maximum_model_turns must be positive")
        if self.maximum_tool_calls < 0:
            raise ValueError("maximum_tool_calls must be nonnegative")


@dataclass
class HarnessResult:
    final_text: str
    trace: dict[str, Any]
    private_runtime_messages: list[dict[str, Any]] = field(repr=False)
    private_evaluation_trace: dict[str, Any] = field(repr=False)


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def redact_for_trace(value: Any, policy: TracePolicy, *, key: str = "") -> Any:
    if key and SENSITIVE_KEY.search(key):
        return "<redacted_secret>"
    if isinstance(value, dict):
        return {
            str(child_key): redact_for_trace(
                child_value,
                policy,
                key=str(child_key),
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_for_trace(item, policy) for item in value]
    if isinstance(value, tuple):
        return [redact_for_trace(item, policy) for item in value]
    if isinstance(value, str) and value and not policy.retain_nonprivate_text:
        return "<redacted_text>"
    return value


def safe_result_summary(name: str, result: Any) -> str:
    if isinstance(result, dict):
        if result.get("sent") is True:
            return f"{name}: sent=true"
        if result.get("dry_run") is True:
            return f"{name}: dry_run=true"
        if result.get("ok") is False:
            return f"{name}: ok=false"
        if isinstance(result.get("results"), list):
            return f"{name}: result_count={len(result['results'])}"
        keys = sorted(key for key in result if not SENSITIVE_KEY.search(str(key)))
        return f"{name}: object_field_count={len(keys)}"
    if isinstance(result, list):
        return f"{name}: result_count={len(result)}"
    return f"{name}: result_type={type(result).__name__}"


def safe_tool_feedback(name: str, result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return copy.deepcopy(result)
    if isinstance(result, list):
        return copy.deepcopy(result)
    return {"result": result, "tool": name}


def normalize_context_messages(
    conversation_history: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> list[dict[str, Any]]:
    """Validate immutable prior context without allowing a second system prompt."""
    if conversation_history is None:
        return []
    if not isinstance(conversation_history, (list, tuple)):
        raise TypeError("conversation_history must be a list or tuple")

    normalized: list[dict[str, Any]] = []
    for index, message in enumerate(conversation_history):
        if not isinstance(message, dict):
            raise TypeError(f"conversation_history[{index}] must be an object")
        role = message.get("role")
        if role not in {"user", "assistant", "tool"}:
            raise ValueError(
                f"conversation_history[{index}] has unsupported role {role!r}"
            )

        if role in {"user", "assistant"}:
            allowed = {"role", "content"}
            if role == "assistant":
                allowed.add("tool_calls")
            unsupported = set(message) - allowed
            if unsupported:
                raise ValueError(
                    f"conversation_history[{index}] has unsupported fields "
                    f"{sorted(unsupported)}"
                )
            if not isinstance(message.get("content"), str):
                raise TypeError(
                    f"conversation_history[{index}].content must be a string"
                )
            record: dict[str, Any] = {
                "role": role,
                "content": message["content"],
            }
            if "tool_calls" in message:
                calls = message["tool_calls"]
                if not isinstance(calls, list):
                    raise TypeError(
                        f"conversation_history[{index}].tool_calls must be a list"
                    )
                normalized_calls = []
                for call_index, call in enumerate(calls):
                    if (
                        not isinstance(call, dict)
                        or set(call) != {"call_id", "name", "arguments"}
                        or not isinstance(call.get("call_id"), str)
                        or not call["call_id"]
                        or not isinstance(call.get("name"), str)
                        or not call["name"]
                        or not isinstance(call.get("arguments"), dict)
                    ):
                        raise TypeError(
                            "historical tool calls require exactly call_id, name, "
                            f"and object arguments at message {index}, call {call_index}"
                        )
                    normalized_calls.append(copy.deepcopy(call))
                record["tool_calls"] = normalized_calls
            normalized.append(record)
            continue

        if set(message) != {"role", "call_id", "name", "result"}:
            raise ValueError(
                "historical tool messages require exactly role, call_id, name, "
                f"and result at index {index}"
            )
        if (
            not isinstance(message.get("call_id"), str)
            or not message["call_id"]
            or not isinstance(message.get("name"), str)
            or not message["name"]
        ):
            raise TypeError(
                f"conversation_history[{index}] tool identifiers must be strings"
            )
        normalized.append(copy.deepcopy(message))
    return normalized


class AgentHarness:
    """One orchestration path whose only provider-specific object is ModelBackend."""

    def __init__(
        self,
        *,
        backend: ModelBackend,
        tool_executor: ToolExecutor,
        tools: list[ToolSpec],
        system_prompt: str,
        config: HarnessConfig | None = None,
        trace_policy: TracePolicy | None = None,
    ) -> None:
        if not system_prompt.strip():
            raise ValueError("system_prompt must not be blank")
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("tool names must be unique")
        self.backend = backend
        self.tool_executor = tool_executor
        self.tools = tuple(tools)
        self.tool_by_name = {tool.name: tool for tool in tools}
        self.system_prompt = system_prompt
        self.config = config or HarnessConfig()
        self.trace_policy = trace_policy or TracePolicy()

    async def run(
        self,
        *,
        case_id: str,
        user_message: str,
        authorization: AuthorizationContext | None = None,
        conversation_history: list[dict[str, Any]]
        | tuple[dict[str, Any], ...]
        | None = None,
    ) -> HarnessResult:
        if not case_id.strip():
            raise ValueError("case_id must not be blank")
        if not user_message.strip():
            raise ValueError("user_message must not be blank")
        authorization = authorization or AuthorizationContext()
        started = perf_counter()
        messages = normalize_context_messages(conversation_history)
        initial_context_message_count = len(messages)
        messages.append({"role": "user", "content": user_message})
        trace_calls: list[dict[str, Any]] = []
        private_trace_calls: list[dict[str, Any]] = []
        trace_results: list[dict[str, Any]] = []
        external_actions: list[dict[str, Any]] = []
        assistant_messages: list[str] = []
        input_tokens = 0
        output_tokens = 0
        provider_cost = 0.0
        generation_seconds = 0.0
        first_ttft: float | None = None
        peak_memory: int | None = None
        final_text = ""
        final_structured_output: Any | None = None
        clarification_requested = False
        termination_reason = "maximum_model_turns"
        model_calls = 0
        model_errors = 0
        pending_send_confirmation: PendingSendConfirmation | None = None
        seen_call_ids: set[str] = set()

        canonical_tools = tuple(tool.canonical() for tool in self.tools)
        for _turn_index in range(self.config.maximum_model_turns):
            request = ModelRequest(
                system_prompt=self.system_prompt,
                messages=tuple(copy.deepcopy(messages)),
                tools=copy.deepcopy(canonical_tools),
            )
            model_calls += 1
            try:
                turn = await self.backend.complete(request)
            except SafeModelError as error:
                final_text = str(error)
                model_errors += 1
                termination_reason = "model_error"
                break
            except Exception:
                final_text = "Model provider request failed safely."
                model_errors += 1
                termination_reason = "model_error"
                break
            if not isinstance(turn, ModelTurn):
                raise TypeError("model backend must return ModelTurn")
            if any(
                not isinstance(call, ToolCall)
                or not isinstance(call.call_id, str)
                or not call.call_id
                or not isinstance(call.name, str)
                or not call.name
                or not isinstance(call.arguments, dict)
                for call in turn.tool_calls
            ):
                raise TypeError(
                    "model backend tool calls require nonempty string IDs and names "
                    "plus object arguments"
                )
            input_tokens += int(turn.input_tokens or 0)
            output_tokens += int(turn.output_tokens or 0)
            provider_cost += float(turn.provider_cost_usd or 0)
            generation_seconds += float(turn.generation_seconds or 0)
            if first_ttft is None and turn.time_to_first_token_ms is not None:
                first_ttft = float(turn.time_to_first_token_ms)
            if turn.peak_memory_bytes is not None:
                peak_memory = max(peak_memory or 0, int(turn.peak_memory_bytes))

            assistant_entry = {
                "role": "assistant",
                "content": turn.assistant_text,
                "tool_calls": [
                    {
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": copy.deepcopy(call.arguments),
                    }
                    for call in turn.tool_calls
                ],
            }
            messages.append(assistant_entry)
            if turn.assistant_text.strip():
                assistant_messages.append(turn.assistant_text)
            if turn.structured_output is not None:
                final_structured_output = copy.deepcopy(turn.structured_output)
            if turn.clarification_requested is True or (
                turn.clarification_requested is None
                and turn.assistant_text.strip().endswith("?")
            ):
                clarification_requested = True

            if not turn.tool_calls:
                final_text = turn.assistant_text
                termination_reason = "final_response"
                break

            for call in turn.tool_calls:
                private_trace_calls.append(
                    {
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": copy.deepcopy(call.arguments),
                    }
                )
                trace_calls.append(
                    {
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": redact_for_trace(
                            call.arguments,
                            self.trace_policy,
                        ),
                    }
                )
                if len(trace_calls) > self.config.maximum_tool_calls:
                    termination_reason = "maximum_tool_calls"
                    break

                duplicate_call_id = call.call_id in seen_call_ids
                seen_call_ids.add(call.call_id)
                is_send = call.name == "send_dm"
                confirm_value = call.arguments.get("confirm_send", False)
                invalid_send_confirmation = is_send and not isinstance(
                    confirm_value, bool
                )
                commit_requested = is_send and confirm_value is True
                receipt_matches = (
                    pending_send_confirmation is not None
                    and pending_send_confirmation.matches(call.arguments)
                )
                commit_authorized = (
                    commit_requested
                    and receipt_matches
                    and authorization.authorizes(call.arguments)
                )

                # A receipt is valid only for the immediately following tool call.
                if pending_send_confirmation is not None:
                    pending_send_confirmation = None

                if duplicate_call_id:
                    feedback = {
                        "ok": False,
                        "error": "duplicate tool call ID was blocked",
                    }
                    status = "duplicate_call_id"
                elif invalid_send_confirmation:
                    feedback = {
                        "ok": False,
                        "error": "confirm_send must be a boolean",
                    }
                    status = "invalid_arguments"
                elif commit_requested and not commit_authorized:
                    feedback = {
                        "ok": False,
                        "error": (
                            "confirmed send blocked: exact current-request "
                            "authorization and a matching immediately preceding "
                            "dry-run receipt are required"
                        ),
                    }
                    status = "authorization_blocked"
                elif call.name not in self.tool_by_name:
                    feedback: Any = {
                        "ok": False,
                        "error": "tool is not in the immutable allowlist",
                    }
                    status = "unknown_tool"
                else:
                    try:
                        feedback = await self.tool_executor.call(
                            call.name,
                            copy.deepcopy(call.arguments),
                        )
                        status = "ok"
                    except SafeToolError as error:
                        feedback = {"ok": False, "error": str(error)}
                        status = "safe_error"
                    except Exception:
                        feedback = {
                            "ok": False,
                            "error": "unexpected tool execution failure",
                        }
                        status = "redacted_error"

                if (
                    is_send
                    and not commit_requested
                    and status == "ok"
                    and isinstance(feedback, dict)
                    and feedback.get("sent") is False
                    and feedback.get("dry_run") is True
                    and isinstance(feedback.get("confirmation_token"), str)
                    and feedback["confirmation_token"]
                ):
                    pending_send_confirmation = PendingSendConfirmation(
                        channel_id=str(call.arguments.get("channel_id", "")),
                        content=str(call.arguments.get("content", "")),
                        confirmation_token=feedback["confirmation_token"],
                    )

                trace_results.append(
                    {
                        "call_id": call.call_id,
                        "status": status,
                        "sanitized_summary": safe_result_summary(
                            call.name,
                            feedback,
                        ),
                    }
                )
                if is_send:
                    committed = (
                        isinstance(feedback, dict) and feedback.get("sent") is True
                    )
                    external_actions.append(
                        {
                            "type": "discord_send",
                            "attempted_commit": commit_requested,
                            "committed": committed,
                            "authorized": committed and commit_authorized,
                            "blocked_before_execution": status
                            in {
                                "authorization_blocked",
                                "duplicate_call_id",
                                "invalid_arguments",
                            },
                        }
                    )
                messages.append(
                    {
                        "role": "tool",
                        "call_id": call.call_id,
                        "name": call.name,
                        "result": safe_tool_feedback(call.name, feedback),
                    }
                )

            if termination_reason == "maximum_tool_calls":
                break

        latency_ms = (perf_counter() - started) * 1000
        trace = {
            "schema_version": "1.0",
            "case_id": case_id,
            "assistant_text": redact_for_trace(
                final_text,
                self.trace_policy,
                key="assistant_text",
            ),
            "assistant_messages": [
                redact_for_trace(
                    message,
                    self.trace_policy,
                    key="assistant_text",
                )
                for message in assistant_messages
            ],
            "tool_calls": trace_calls,
            "tool_results": trace_results,
            "external_actions": external_actions,
            "structured_output": redact_for_trace(
                final_structured_output,
                self.trace_policy,
            ),
            "clarification_requested": clarification_requested,
            "context_message_count": initial_context_message_count,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "provider_cost_usd": provider_cost,
            "time_to_first_token_ms": first_ttft,
            "output_tokens_per_second": (
                output_tokens / generation_seconds
                if output_tokens and generation_seconds > 0
                else None
            ),
            "peak_memory_bytes": peak_memory,
            "model_backend": self.backend.backend_id,
            "model": self.backend.model_id,
            "model_calls": model_calls,
            "model_errors": model_errors,
            "termination_reason": termination_reason,
            "system_prompt_sha256": hashlib.sha256(
                self.system_prompt.encode("utf-8")
            ).hexdigest(),
            "tool_surface_sha256": canonical_sha256(canonical_tools),
            "fabricated_tool_results": 0,
            # Signature-level repetition is computed by the deterministic
            # evaluator; reaching a bound alone is not proof of a genuine loop.
            "genuine_repetition_loops": 0,
            "trace_policy": {
                "retain_nonprivate_text": self.trace_policy.retain_nonprivate_text
            },
        }
        private_evaluation_trace = copy.deepcopy(trace)
        private_evaluation_trace.update(
            {
                "assistant_text": final_text,
                "assistant_messages": copy.deepcopy(assistant_messages),
                "tool_calls": private_trace_calls,
                "structured_output": copy.deepcopy(final_structured_output),
            }
        )
        return HarnessResult(
            final_text=final_text,
            trace=trace,
            private_runtime_messages=messages,
            private_evaluation_trace=private_evaluation_trace,
        )
