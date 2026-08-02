from __future__ import annotations

import json
import os
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from anthropic import Anthropic


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class ModelResponse:
    text: str | None = None
    tool_calls: list[ToolCall] | None = None
    assistant_content: list[dict[str, Any]] | None = None
    stop_reason: str = "end_turn"


class ModelProvider(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
        system: str | None = None,
    ) -> ModelResponse: ...


def _content_block_to_dict(block: Any) -> dict[str, Any]:
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    if hasattr(block, "dict"):
        return block.dict(exclude_none=True)
    data = {"type": block.type}
    for name in ("text", "id", "name", "input", "thinking", "signature"):
        if hasattr(block, name):
            data[name] = getattr(block, name)
    return data


class AnthropicProvider:
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-latest",
        max_tokens: int = 4096,
        base_url: str | None = None,
    ) -> None:
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or "mock-key-for-local"
        )

        self.model = model
        self.max_tokens = max_tokens
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")
        self.client = Anthropic(api_key=api_key, base_url=self.base_url)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
        system: str | None = None,
    ) -> ModelResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)

        response = self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        assistant_content: list[dict[str, Any]] = []

        for block in response.content:
            assistant_content.append(_content_block_to_dict(block))
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        return ModelResponse(
            text="\n".join(text_parts) or None,
            tool_calls=tool_calls or None,
            assistant_content=assistant_content or None,
            stop_reason=response.stop_reason or "end_turn",
        )


class OllamaProvider:
    def __init__(self, model: str = "gemma3:4b", base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
        system: str | None = None,
    ) -> ModelResponse:
        # Convert Anthropic message layout to Ollama Chat API layout
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "assistant":
                tool_calls_out = []
                text_out = []
                if isinstance(content, list):
                    for block in content:
                        if block["type"] == "text":
                            text_out.append(block["text"])
                        elif block["type"] == "tool_use":
                            tool_calls_out.append(
                                {
                                    "id": block["id"],
                                    "type": "function",
                                    "function": {
                                        "name": block["name"],
                                        "arguments": block["input"],
                                    },
                                }
                            )
                else:
                    text_out.append(str(content))

                mapped_msg: dict[str, Any] = {"role": "assistant"}
                if text_out:
                    mapped_msg["content"] = "\n".join(text_out)
                if tool_calls_out:
                    mapped_msg["tool_calls"] = tool_calls_out
                ollama_messages.append(mapped_msg)
            elif role == "user":
                if (
                    isinstance(content, list)
                    and content
                    and content[0].get("type") == "tool_result"
                ):
                    # Maps tool results back to OpenAI/Ollama role="tool"
                    for block in content:
                        ollama_messages.append(
                            {
                                "role": "tool",
                                "name": block.get("name", "tool"),
                                "tool_call_id": block["tool_use_id"],
                                "content": block["content"],
                            }
                        )
                else:
                    ollama_messages.append({"role": "user", "content": str(content)})
            else:
                ollama_messages.append({"role": role, "content": str(content)})

        payload = {"model": self.model, "messages": ollama_messages, "stream": False}
        if tools:
            payload["tools"] = _to_openai_tools(tools)

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as res:
                res_data = json.loads(res.read().decode("utf-8"))

            msg_data = res_data.get("message", {})
            text = msg_data.get("content") or None
            tool_calls = []
            assistant_content = []

            if text:
                assistant_content.append({"type": "text", "text": text})

            raw_tool_calls = msg_data.get("tool_calls", [])
            for tc in raw_tool_calls:
                tc_func = tc.get("function", {})
                tc_id = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                tc_name = tc_func.get("name")
                tc_args = tc_func.get("arguments") or {}
                if isinstance(tc_args, str):
                    try:
                        tc_args = json.loads(tc_args)
                    except json.JSONDecodeError:
                        tc_args = {}

                tool_calls.append(ToolCall(id=tc_id, name=tc_name, arguments=tc_args))
                assistant_content.append(
                    {"type": "tool_use", "id": tc_id, "name": tc_name, "input": tc_args}
                )

            return ModelResponse(
                text=text,
                tool_calls=tool_calls or None,
                assistant_content=assistant_content or None,
                stop_reason="tool_use" if tool_calls else "end_turn",
            )
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with Ollama: {e}. Is Ollama running?")


class MockProvider:
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
        system: str | None = None,
    ) -> ModelResponse:
        last = messages[-1]
        if last["role"] == "user":
            content = last["content"]
            if isinstance(content, list) and content and content[0].get("type") == "tool_result":
                return ModelResponse(text=f"Дякую за виконання. Результат: {content[0]['content']}")

            text = str(content)
            if "скажи привіт" in text.lower() or "say hi" in text.lower():
                return ModelResponse(
                    tool_calls=[
                        ToolCall(
                            id="call_echo_1",
                            name="echo",
                            arguments={"text": "Привіт від локального ШІ-агента!"},
                        )
                    ],
                    stop_reason="tool_use",
                )
            return ModelResponse(
                text="Я можу відповісти вам безпосередньо. Як я можу допомогти вам сьогодні?"
            )

        if last["role"] == "tool":
            return ModelResponse(text=f"Результат інструменту: {last['content']}")

        return ModelResponse(text="Вітаю в симуляції ШІ-агента.")


def _to_anthropic_tools(tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in tools
    ]


def _to_openai_tools(tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def create_provider(name: str, model: str, base_url: str | None = None) -> ModelProvider:
    if name == "anthropic":
        return AnthropicProvider(model=model, base_url=base_url)
    if name == "ollama":
        return OllamaProvider(model=model, base_url=base_url or "http://localhost:11434")
    if name == "mock":
        return MockProvider()
    raise ValueError(f"Unknown provider name: {name}")
