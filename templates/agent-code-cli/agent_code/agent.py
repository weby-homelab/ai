from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console

from .compact_basic import compact
from .fs_safety import (
    SkipPolicy,
    apply_single_replace,
    check_mtime_conflict,
    ensure_read_before_edit,
    load_gitignore,
    resolve_in_cwd,
)
from .model import ModelProvider, ModelResponse, ToolResult
from .permissions import PermissionRequest, decide_permission
from .prompt_ui import (
    confirm_command,
    confirm_edit,
    confirm_tool_use,
    prompt_single_choice,
    render_diff,
)
from .session import Session
from .tools import ToolContext, ToolRegistry

console = Console()


@dataclass
class AgentResult:
    final: str
    trace: list[str]
    messages: list[dict[str, Any]]


_SYSTEM_CORE = (
    "You are an AI coding agent running inside a CLI harness. "
    "You have access to tools for reading/writing files, running shell commands, "
    "searching the web, and asking the user questions. "
    "Use tools when needed; respond directly when you can."
)


def build_system_prompt(cwd: Path) -> str:
    parts = [_SYSTEM_CORE]

    # Check if a custom AGENT.md exists to load project specific rules
    agent_md = cwd / "AGENT.md"
    if agent_md.exists():
        try:
            parts.append(
                f"<project-rules>\n{agent_md.read_text(encoding='utf-8')}\n</project-rules>"
            )
        except Exception:
            pass

    return "\n\n".join(parts)


def _assistant_message(response: ModelResponse) -> dict[str, Any]:
    if response.assistant_content:
        return {"role": "assistant", "content": response.assistant_content}

    content = []
    if response.text:
        content.append({"type": "text", "text": response.text})
    for call in response.tool_calls or []:
        content.append(
            {
                "type": "tool_use",
                "id": call.id,
                "name": call.name,
                "input": call.arguments,
            }
        )
    return {"role": "assistant", "content": content}


def _tool_result_message(tool_call_id: str, content: str, is_error: bool = False) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": content,
                "is_error": is_error,
            }
        ],
    }


def run_agent(
    prompt: str,
    provider: ModelProvider,
    tools: ToolRegistry,
    max_steps: int = 8,
    cwd: Path | None = None,
    permission_mode: str = "default",
    session: Session | None = None,
    system_prompt: str | None = None,
) -> AgentResult:
    resolved_cwd = cwd or Path.cwd()
    ctx = ToolContext(
        cwd=resolved_cwd,
        skip_policy=SkipPolicy.default(gitignore=load_gitignore(resolved_cwd)),
    )

    def emit(line: str) -> None:
        trace.append(line)
        console.print(line, markup=False)

    if session and session.history:
        messages = list(session.history)
        messages.append({"role": "user", "content": prompt})
    else:
        messages = [{"role": "user", "content": prompt}]

    if session:
        session.append_messages([messages[-1]])

    trace = []
    for step in range(max_steps):
        # Compact context if dialog history becomes too long (over 40 turns)
        if len(messages) > 40:
            messages = compact(messages, keep=8)
            console.print(f"[dim]compacted: {len(messages)} messages remaining[/dim]")

        response = provider.complete(messages, tools=tools.list(), system=system_prompt)
        messages.append(_assistant_message(response))

        if not response.tool_calls:
            final = response.text or ""
            emit(f"final: {final}")
            if session:
                session.append_messages([messages[-1]])
            return AgentResult(final=final, trace=trace, messages=messages)

        tool_result_blocks = []
        for call in response.tool_calls:
            emit(f"tool_call: {call.name} {call.arguments}")

            # Check permissions
            request = PermissionRequest(
                tool_name=call.name,
                args=call.arguments,
                mode=permission_mode,
                cwd=ctx.cwd,
            )
            decision = decide_permission(request)

            edit_preview = None
            if call.name in ("file_write", "file_edit") and decision.behavior != "deny":
                path_str = call.arguments.get("file_path", "")
                if not path_str:
                    result = ToolResult(
                        call.id,
                        "error: missing required argument 'file_path'",
                        is_error=True,
                    )
                    emit(f"observation: {result.content}")
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": result.tool_call_id,
                            "content": result.content,
                            "is_error": True,
                        }
                    )
                    continue

                try:
                    path = resolve_in_cwd(ctx.cwd, path_str)
                except (ValueError, OSError) as exc:
                    result = ToolResult(call.id, f"error: {exc}", is_error=True)
                    emit(f"observation: {result.content}")
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": result.tool_call_id,
                            "content": result.content,
                            "is_error": True,
                        }
                    )
                    continue

                old_content = path.read_text(encoding="utf-8") if path.exists() else ""

                validation_error = None
                if call.name == "file_write":
                    if path.exists():
                        validation_error = ensure_read_before_edit(
                            ctx.read_state, path
                        ) or check_mtime_conflict(ctx.read_state, path)
                    new_content = call.arguments.get("content", "")
                else:  # file_edit
                    new_content = ""
                    if not path.exists():
                        validation_error = f"error: file does not exist: {path_str}"
                    else:
                        validation_error = ensure_read_before_edit(
                            ctx.read_state, path
                        ) or check_mtime_conflict(ctx.read_state, path)
                    if validation_error is None:
                        new_content, replace_err = apply_single_replace(
                            old_content,
                            call.arguments.get("old_string", ""),
                            call.arguments.get("new_string", ""),
                            bool(call.arguments.get("replace_all", False)),
                        )
                        if replace_err is not None:
                            validation_error = replace_err

                if validation_error is not None:
                    result = ToolResult(call.id, validation_error, is_error=True)
                    emit(f"observation: {result.content}")
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": result.tool_call_id,
                            "content": result.content,
                            "is_error": True,
                        }
                    )
                    continue

                edit_preview = (path_str, old_content, new_content)

            if decision.behavior == "deny":
                result = ToolResult(call.id, f"error: {decision.message}", is_error=True)
                emit(f"observation: {result.content}")
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": result.tool_call_id,
                        "content": result.content,
                        "is_error": True,
                    }
                )
                continue

            elif decision.behavior == "ask":
                if call.name in ("file_write", "file_edit"):
                    if edit_preview is not None:
                        path_str, old_content, new_content = edit_preview
                        diff_text = render_diff(old_content, new_content, path_str)
                        console.print(f"\n[bold]Diff for {path_str}:[/bold]")
                        console.print(diff_text)
                        if not confirm_edit(path_str):
                            result = ToolResult(
                                call.id, "error: edit rejected by user", is_error=True
                            )
                            emit(f"observation: {result.content}")
                            tool_result_blocks.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": result.tool_call_id,
                                    "content": result.content,
                                    "is_error": True,
                                }
                            )
                            continue

                elif call.name == "bash":
                    command = call.arguments.get("command", "")
                    if not confirm_command(command):
                        result = ToolResult(
                            call.id, "error: command rejected by user", is_error=True
                        )
                        emit(f"observation: {result.content}")
                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": result.tool_call_id,
                                "content": result.content,
                                "is_error": True,
                            }
                        )
                        continue

                elif call.name in ("web_fetch", "web_search"):
                    detail = (
                        call.arguments.get("url")
                        or call.arguments.get("query")
                        or str(call.arguments)
                    )
                    if not confirm_tool_use(call.name, detail):
                        result = ToolResult(
                            call.id, "error: tool use rejected by user", is_error=True
                        )
                        emit(f"observation: {result.content}")
                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": result.tool_call_id,
                                "content": result.content,
                                "is_error": True,
                            }
                        )
                        continue

                elif call.name == "ask_user_question":
                    question = call.arguments.get("prompt", "")
                    options = call.arguments.get("options", [])
                    if not isinstance(options, list):
                        options = []
                    labels = [str(o) for o in options]
                    selected = prompt_single_choice(question, labels)
                    if selected is None:
                        result = ToolResult(call.id, "User skipped the question.", is_error=False)
                    else:
                        result = ToolResult(call.id, f'User selected: "{selected}"', is_error=False)
                    emit(f"observation: {result.content}")
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": result.tool_call_id,
                            "content": result.content,
                            "is_error": result.is_error,
                        }
                    )
                    continue

            result = tools.run(call, ctx)
            emit(f"observation: {result.content}")
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": result.tool_call_id,
                    "content": result.content,
                    "is_error": result.is_error,
                }
            )

        messages.append({"role": "user", "content": tool_result_blocks})
        if session:
            session.append_messages(messages[-2:])

    final = f"reached max_steps={max_steps}"
    emit(f"final: {final}")
    return AgentResult(final=final, trace=trace, messages=messages)
