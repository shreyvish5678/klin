#!/usr/bin/env python3
"""Hosted and local model-boundary adapters for the immutable agent harness."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from time import perf_counter
from typing import Any

try:
    from model_harness import (
        ModelRequest,
        ModelTurn,
        SafeModelError,
        ToolCall,
    )
except ModuleNotFoundError:
    from tools.model_harness import (
        ModelRequest,
        ModelTurn,
        SafeModelError,
        ToolCall,
    )


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "research" / "workflowdistill-discord-validation"
DEFAULT_TURN_SCHEMA = RUN_DIR / "artifacts" / "harness" / "model-turn.schema.json"
DEFAULT_CODEX_CWD = RUN_DIR / "sandbox" / "hosted-control"


def _tool_call_from_envelope(record: dict[str, Any]) -> ToolCall:
    if set(record) != {"call_id", "name", "arguments_json"}:
        raise SafeModelError("Hosted model returned an invalid tool-call envelope.")
    try:
        arguments = json.loads(record["arguments_json"])
    except (TypeError, json.JSONDecodeError) as error:
        raise SafeModelError(
            "Hosted model returned invalid JSON tool arguments."
        ) from error
    if (
        not isinstance(record["call_id"], str)
        or not record["call_id"]
        or not isinstance(record["name"], str)
        or not record["name"]
        or not isinstance(arguments, dict)
    ):
        raise SafeModelError("Hosted model returned malformed tool-call fields.")
    return ToolCall(
        call_id=record["call_id"],
        name=record["name"],
        arguments=arguments,
    )


def _model_boundary_prompt(request: ModelRequest) -> str:
    envelope = {
        "immutable_system_instructions": request.system_prompt,
        "conversation": request.messages,
        "available_tools": request.tools,
    }
    return (
        "Act only as the model boundary inside an already-implemented agent loop. "
        "Do not use Codex tools, shell, files, browsing, plugins, apps, or hidden "
        "capabilities. Never execute a listed application tool yourself and never "
        "invent its result. Read the immutable instructions, conversation, and tool "
        "schemas in the JSON payload below. For this single model turn, either "
        "return a final assistant_text with no tool calls, or request the necessary "
        "application tool calls. Encode each tool's arguments as a compact JSON "
        "object string in arguments_json. Use a unique nonempty call_id. Set "
        "clarification_requested true only when the assistant_text asks the user for "
        "missing information. Return only the required structured envelope.\n\n"
        + json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    )


class CodexExecBackend:
    """Authenticated OpenAI Responses control through the installed Codex client."""

    backend_id = "openai-responses-via-codex"

    def __init__(
        self,
        *,
        model_id: str = "gpt-5.6-sol",
        reasoning_effort: str = "medium",
        codex_path: str = "codex",
        output_schema: Path = DEFAULT_TURN_SCHEMA,
        cwd: Path = DEFAULT_CODEX_CWD,
        timeout_seconds: float = 120,
        input_usd_per_million: float | None = None,
        cached_input_usd_per_million: float | None = None,
        output_usd_per_million: float | None = None,
    ) -> None:
        self.model_id = model_id
        self.reasoning_effort = reasoning_effort
        self.codex_path = codex_path
        self.output_schema = output_schema.resolve()
        self.cwd = cwd.resolve()
        self.timeout_seconds = timeout_seconds
        self.input_usd_per_million = input_usd_per_million
        self.cached_input_usd_per_million = cached_input_usd_per_million
        self.output_usd_per_million = output_usd_per_million
        if not self.output_schema.is_file():
            raise ValueError("Hosted model turn schema is missing")
        self.cwd.mkdir(parents=True, exist_ok=True)

    async def complete(self, request: ModelRequest) -> ModelTurn:
        return await asyncio.to_thread(self._complete_sync, request)

    def _complete_sync(self, request: ModelRequest) -> ModelTurn:
        prompt = _model_boundary_prompt(request)
        started = perf_counter()
        with tempfile.TemporaryDirectory(
            prefix="workflowdistill-hosted-turn-",
            dir=self.cwd,
        ) as temporary:
            output_path = Path(temporary) / "turn.json"
            command = [
                self.codex_path,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--disable",
                "shell_tool",
                "--model",
                self.model_id,
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "--output-schema",
                str(self.output_schema),
                "--output-last-message",
                str(output_path),
                "--json",
                "-",
            ]
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    cwd=self.cwd,
                    env=os.environ.copy(),
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise SafeModelError(
                    "Hosted model request did not complete within its safe boundary."
                ) from error
            latency = perf_counter() - started
            if completed.returncode != 0 or not output_path.is_file():
                raise SafeModelError("Hosted model request failed safely.")

            usage: dict[str, int] = {}
            internal_tool_used = False
            for line in completed.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "item.completed":
                    item_type = (event.get("item") or {}).get("type")
                    if item_type not in {"agent_message", "reasoning"}:
                        internal_tool_used = True
                if event.get("type") == "turn.completed":
                    usage = event.get("usage") or {}
            if internal_tool_used:
                raise SafeModelError(
                    "Hosted control crossed the model-only execution boundary."
                )

            try:
                envelope = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise SafeModelError(
                    "Hosted model returned an invalid structured envelope."
                ) from error
            if set(envelope) != {
                "assistant_text",
                "tool_calls",
                "clarification_requested",
            }:
                raise SafeModelError(
                    "Hosted model returned an unexpected structured envelope."
                )
            if (
                not isinstance(envelope["assistant_text"], str)
                or not isinstance(envelope["tool_calls"], list)
                or not isinstance(envelope["clarification_requested"], bool)
            ):
                raise SafeModelError(
                    "Hosted model returned invalid structured field types."
                )
            tool_calls = tuple(
                _tool_call_from_envelope(record)
                for record in envelope["tool_calls"]
                if isinstance(record, dict)
            )
            if len(tool_calls) != len(envelope["tool_calls"]):
                raise SafeModelError("Hosted model returned a malformed tool call.")

            input_tokens = int(usage.get("input_tokens") or 0)
            cached_input_tokens = int(usage.get("cached_input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
            cost = self._cost(
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
            )
            return ModelTurn(
                assistant_text=envelope["assistant_text"],
                tool_calls=tool_calls,
                clarification_requested=envelope["clarification_requested"],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider_cost_usd=cost,
                generation_seconds=latency,
            )

    def _cost(
        self,
        *,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
    ) -> float | None:
        if (
            self.input_usd_per_million is None
            or self.cached_input_usd_per_million is None
            or self.output_usd_per_million is None
        ):
            return None
        uncached = max(0, input_tokens - cached_input_tokens)
        return (
            uncached * self.input_usd_per_million
            + cached_input_tokens * self.cached_input_usd_per_million
            + output_tokens * self.output_usd_per_million
        ) / 1_000_000


def _chat_messages(request: ModelRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": request.system_prompt}
    ]
    for message in request.messages:
        role = message["role"]
        if role in {"user", "assistant"}:
            converted: dict[str, Any] = {
                "role": role,
                "content": message.get("content", ""),
            }
            if role == "assistant" and message.get("tool_calls"):
                converted["tool_calls"] = [
                    {
                        "id": call["call_id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(
                                call["arguments"],
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    }
                    for call in message["tool_calls"]
                ]
            messages.append(converted)
            continue
        if role == "tool":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": message["call_id"],
                    "name": message["name"],
                    "content": json.dumps(
                        message["result"],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
            )
            continue
        raise SafeModelError("Local model received an unsupported message role.")
    return messages


class OpenAICompatibleChatBackend:
    """Local OpenAI-compatible chat-completions model boundary."""

    backend_id = "local-openai-compatible"

    def __init__(
        self,
        *,
        model_id: str,
        endpoint: str = "http://127.0.0.1:8081/v1/chat/completions",
        timeout_seconds: float = 120,
        temperature: float = 0,
    ) -> None:
        self.model_id = model_id
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    async def complete(self, request: ModelRequest) -> ModelTurn:
        return await asyncio.to_thread(self._complete_sync, request)

    def _complete_sync(self, request: ModelRequest) -> ModelTurn:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in request.tools
        ]
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": _chat_messages(request),
            "tools": tools,
            "tool_choice": "auto",
            "temperature": self.temperature,
            "stream": False,
        }
        started = perf_counter()
        http_request = urllib.request.Request(
            self.endpoint,
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        try:
            with urllib.request.urlopen(
                http_request,
                timeout=self.timeout_seconds,
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (
            OSError,
            TimeoutError,
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
        ) as error:
            raise SafeModelError("Local model endpoint request failed safely.") from error
        elapsed = perf_counter() - started
        try:
            message = body["choices"][0]["message"]
            usage = body.get("usage") or {}
            tool_calls = tuple(
                ToolCall(
                    call_id=record["id"],
                    name=record["function"]["name"],
                    arguments=json.loads(record["function"]["arguments"]),
                )
                for record in message.get("tool_calls") or []
            )
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise SafeModelError(
                "Local model returned an invalid chat-completions response."
            ) from error
        assistant_text = message.get("content") or ""
        if not isinstance(assistant_text, str):
            raise SafeModelError("Local model returned invalid assistant content.")
        return ModelTurn(
            assistant_text=assistant_text,
            tool_calls=tool_calls,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            generation_seconds=elapsed,
        )
