from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PermissionRequest:
    tool_name: str
    args: dict
    mode: str
    cwd: Path


@dataclass
class PermissionDecision:
    behavior: str  # "allow" | "ask" | "deny"
    message: str | None = None


_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+-rf", "rm -rf is destructive"),
    (r"rm\s+-fr", "rm -fr is destructive"),
    (r"\bsudo\b", "sudo grants root access"),
    (r"chmod\s+-R", "chmod -R is recursive permission change"),
    (
        r"(curl|wget).*\|.*(sh|bash|zsh)\b",
        "downloaded script execution may execute untrusted code",
    ),
    (r"git\s+push\s+.*--force", "git push --force overwrites remote history"),
    (r"git\s+push\s+-f", "git push -f overwrites remote history"),
    (r"\bgit\s+push\b", "git push publishes local changes to a remote"),
    (r"git\s+reset\s+--hard", "git reset --hard discards uncommitted changes"),
]


def _is_dangerous(command: str) -> str | None:
    for pattern, reason in _DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None


_READONLY_TOOLS = frozenset(
    {
        "read_file",
        "list_files",
        "glob",
        "grep",
        "project_tree",
        "git_status",
        "git_diff",
        "system_date",
        "echo",
    }
)

_LOW_RISK_WRITES = frozenset({"memory_write", "memory_recall"})

_ASK_TOOLS = frozenset({"ask_user_question", "web_fetch", "web_search"})


def decide_permission(request: PermissionRequest) -> PermissionDecision:
    tool_name = request.tool_name
    args = request.args
    mode = request.mode

    if tool_name in _ASK_TOOLS:
        return PermissionDecision("ask")

    if mode == "plan":
        if tool_name in _READONLY_TOOLS:
            return PermissionDecision("allow")
        return PermissionDecision(
            "deny",
            f"plan mode: {tool_name} is not allowed. Only read-only tools can run in plan mode.",
        )

    if tool_name in _READONLY_TOOLS:
        return PermissionDecision("allow")

    if tool_name in _LOW_RISK_WRITES:
        return PermissionDecision("allow")

    if tool_name == "bash":
        command = args.get("command", "")
        danger_reason = _is_dangerous(command)
        if danger_reason:
            return PermissionDecision("deny", f"Dangerous command blocked: {danger_reason}")

    if mode == "acceptEdits" and tool_name in ("file_write", "file_edit"):
        return PermissionDecision("allow")

    # Default behavior for writes and commands is to ask the user
    return PermissionDecision("ask")
