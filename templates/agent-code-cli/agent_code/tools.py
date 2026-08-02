from __future__ import annotations

import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import html2text
except ImportError:
    html2text = None

from .fs_safety import (
    ReadFileState,
    SkipPolicy,
    apply_single_replace,
    backup,
    ensure_text_file,
    ensure_within_size,
    resolve_in_cwd,
    should_skip,
    truncate_output,
)
from .model import ToolCall, ToolResult


@dataclass
class ToolContext:
    cwd: Path
    skip_policy: SkipPolicy
    read_state: ReadFileState = ReadFileState()


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: Any,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    def run(self, args: dict[str, Any], ctx: ToolContext) -> str:
        try:
            return self.func(args, ctx)
        except Exception as e:
            return f"error: {e}"


def echo(args: dict[str, Any], ctx: ToolContext) -> str:
    return args.get("text", "")


def system_date(args: dict[str, Any], ctx: ToolContext) -> str:
    import datetime

    return datetime.datetime.now().isoformat()


def read_file(args: dict[str, Any], ctx: ToolContext) -> str:
    path_str = args.get("path", "")
    if not path_str:
        return "error: missing required argument 'path'"
    try:
        path = resolve_in_cwd(ctx.cwd, path_str)
        ensure_text_file(path)
        ensure_within_size(path)
        content = path.read_text(encoding="utf-8", errors="replace")
        ctx.read_state.record(path, content)
        return content
    except Exception as e:
        return f"error: {e}"


def list_files(args: dict[str, Any], ctx: ToolContext) -> str:
    path_str = args.get("path", ".")
    try:
        base = resolve_in_cwd(ctx.cwd, path_str)
        if not base.is_dir():
            return f"error: not a directory: {path_str}"

        lines = []
        for p in base.iterdir():
            rel = p.relative_to(ctx.cwd)
            if should_skip(rel, ctx.skip_policy):
                continue
            suffix = "/" if p.is_dir() else ""
            lines.append(f"{rel.name}{suffix}")
        return "\n".join(sorted(lines)) if lines else "(empty directory)"
    except Exception as e:
        return f"error: {e}"


def glob(args: dict[str, Any], ctx: ToolContext) -> str:
    pattern = args.get("pattern", "")
    if not pattern:
        return "error: missing required argument 'pattern'"
    try:
        lines = []
        for p in ctx.cwd.glob(pattern):
            rel = p.relative_to(ctx.cwd)
            if should_skip(rel, ctx.skip_policy):
                continue
            suffix = "/" if p.is_dir() else ""
            lines.append(f"{rel}{suffix}")
        return "\n".join(sorted(lines)) if lines else "(no matches)"
    except Exception as e:
        return f"error: {e}"


def grep(args: dict[str, Any], ctx: ToolContext) -> str:
    pattern = args.get("pattern", "")
    if not pattern:
        return "error: missing required argument 'pattern'"
    path_str = args.get("path", ".")
    ignore_case = bool(args.get("ignore_case", False))
    glob_arg = args.get("glob", None)

    try:
        base = resolve_in_cwd(ctx.cwd, path_str)
    except Exception as e:
        return f"error: {e}"

    # Try ripgrep first
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=True)
        return _grep_ripgrep(pattern, base, glob_arg, ignore_case, ctx)
    except (subprocess.SubprocessError, OSError):
        return _grep_python(pattern, base, glob_arg, ignore_case, ctx)


def _grep_ripgrep(
    pattern: str,
    base: Path,
    glob_arg: str | None,
    ignore_case: bool,
    ctx: ToolContext,
) -> str:
    args = ["rg", "--line-number", "--no-heading"]
    if ignore_case:
        args.append("--ignore-case")
    for name in ctx.skip_policy.skip_dirs:
        args.extend(["--glob", f"!{name}/**"])
    if glob_arg:
        args.extend(["--glob", glob_arg])
    args.append(pattern)
    args.append(str(base))

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except Exception as e:
        return f"error: {e}"

    if proc.returncode not in (0, 1):
        return f"error: rg: {proc.stderr.strip() or proc.returncode}"

    # relativize paths in output
    cwd_prefix = f"{ctx.cwd}/"
    lines = [line.removeprefix(cwd_prefix) for line in proc.stdout.splitlines()]
    return truncate_output("\n".join(lines).strip() or "(no matches)")


def _grep_python(
    pattern: str,
    base: Path,
    glob_arg: str | None,
    ignore_case: bool,
    ctx: ToolContext,
) -> str:
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        return f"error: invalid regex: {exc}"

    if base.is_file():
        candidates = [base]
    else:
        candidates = []
        try:
            for path in base.rglob(glob_arg or "*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(ctx.cwd)
                if should_skip(rel, ctx.skip_policy):
                    continue
                candidates.append(path)
        except Exception as e:
            return f"error: {e}"

    hits = []
    for path in candidates:
        try:
            ensure_text_file(path)
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = path.relative_to(ctx.cwd)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                hits.append(f"{rel}:{lineno}:{line}")
    return truncate_output("\n".join(hits) or "(no matches)")


def project_tree(args: dict[str, Any], ctx: ToolContext) -> str:
    max_depth = int(args.get("max_depth", 3))
    max_nodes = 200
    lines = [f"{ctx.cwd.name}/"]
    nodes = 0

    def walk(directory: Path, depth: int) -> None:
        nonlocal nodes
        if depth > max_depth:
            return
        try:
            children = sorted(
                (
                    c
                    for c in directory.iterdir()
                    if not should_skip(c.relative_to(ctx.cwd), ctx.skip_policy)
                ),
                key=lambda p: (not p.is_dir(), p.name),
            )
        except OSError:
            return

        for child in children:
            if nodes >= max_nodes:
                if nodes == max_nodes:
                    lines.append("  " * depth + "...[truncated]")
                    nodes += 1
                return
            suffix = "/" if child.is_dir() else ""
            lines.append("  " * depth + child.name + suffix)
            nodes += 1
            if child.is_dir():
                walk(child, depth + 1)

    walk(ctx.cwd, 1)
    return "\n".join(lines)


def _html_to_markdown(html: str) -> str:
    if html2text is not None:
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        return converter.handle(html)

    # Very simple regex-based fallback if html2text isn't installed
    text = re.sub(
        r"<style[^>]*>.*?</style[^>]*>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<script[^>]*>.*?</script[^>]*>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def web_fetch(args: dict[str, Any], ctx: ToolContext) -> str:
    url = args.get("url", "")
    if not url:
        return "error: missing required argument 'url'"

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-HomeLabAgent/1.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as res:
            charset = res.headers.get_content_charset() or "utf-8"
            html_content = res.read().decode(charset, errors="replace")
            content_type = res.headers.get_content_type() or ""

        if "html" in content_type:
            markdown = _html_to_markdown(html_content)
        else:
            markdown = html_content

        return truncate_output(markdown)
    except Exception as e:
        return f"error: {e}"


def web_search(args: dict[str, Any], ctx: ToolContext) -> str:
    query = args.get("query", "")
    if not query:
        return "error: missing required argument 'query'"
    max_results = max(1, min(int(args.get("max_results", 5)), 10))

    try:
        # Crawl DuckDuckGo HTML search page
        enc_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={enc_query}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            html = res.read().decode("utf-8", errors="replace")

        pattern = re.compile(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        results = []
        for href, title_html in pattern.findall(html):
            title = re.sub(r"<[^>]+>", "", title_html).strip()

            # Extract target URL from DuckDuckGo wrapper
            parsed_href = urllib.parse.urlparse(
                href if href.startswith("http") else f"https:{href}"
            )
            params = urllib.parse.parse_qs(parsed_href.query)
            target_url = params["uddg"][0] if "uddg" in params else href

            results.append(f"- {title}\n  {target_url}")
            if len(results) >= max_results:
                break

        return truncate_output("\n".join(results) or "(no results)")
    except Exception as e:
        return f"error: {e}"


def file_write(args: dict[str, Any], ctx: ToolContext) -> str:
    path_str = args.get("file_path", "")
    content = args.get("content", "")
    if not path_str:
        return "error: missing required argument 'file_path'"
    try:
        path = resolve_in_cwd(ctx.cwd, path_str)
    except ValueError as exc:
        return f"error: {exc}"

    if path.exists():
        try:
            old = path.read_text(encoding="utf-8")
            backup(ctx.cwd, path, old)
        except Exception:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    ctx.read_state.record(path, content)
    return f"Wrote {len(content)} chars to {path_str}"


def file_edit(args: dict[str, Any], ctx: ToolContext) -> str:
    path_str = args.get("file_path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = bool(args.get("replace_all", False))

    if not path_str:
        return "error: missing required argument 'file_path'"
    try:
        path = resolve_in_cwd(ctx.cwd, path_str)
    except ValueError as exc:
        return f"error: {exc}"

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"error: {exc}"

    backup(ctx.cwd, path, content)
    new_content, err = apply_single_replace(content, old_string, new_string, replace_all)
    if err:
        return err

    path.write_text(new_content, encoding="utf-8")
    ctx.read_state.record(path, new_content)
    return f"Edited {path_str}: replaced {len(old_string)} chars with {len(new_string)} chars"


def _git_status(args: dict[str, Any], ctx: ToolContext) -> str:
    return _bash_run_sync("git status", ctx.cwd)


def _git_diff(args: dict[str, Any], ctx: ToolContext) -> str:
    return _bash_run_sync("git diff", ctx.cwd)


def _bash_run_sync(command: str, cwd: Path, timeout: int = 15) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = []
        if proc.stdout:
            out.append(proc.stdout)
        if proc.stderr:
            out.append(proc.stderr)
        return "".join(out).strip() or f"(exit code {proc.returncode})"
    except subprocess.TimeoutExpired:
        return "error: command execution timed out"
    except Exception as e:
        return f"error: {e}"


def bash(args: dict[str, Any], ctx: ToolContext) -> str:
    command = args.get("command", "")
    if not command:
        return "error: missing required argument 'command'"
    timeout = int(args.get("timeout", 30))
    return _bash_run_sync(command, ctx.cwd, timeout=timeout)


def _ask_user_question(args: dict[str, Any], ctx: ToolContext) -> str:
    return "error: ask_user_question must be handled by the harness, not executed directly"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def run(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id,
                content=f"unknown tool: {call.name}",
                is_error=True,
            )
        res = tool.run(call.arguments, ctx)
        is_err = res.startswith("error:")
        return ToolResult(tool_call_id=call.id, content=res, is_error=is_err)


def default_tools() -> ToolRegistry:
    reg = ToolRegistry()

    # 1. system date
    reg.register(Tool("system_date", "Get the current system date and time.", {}, system_date))

    # 2. echo
    reg.register(
        Tool(
            "echo",
            "Echo back input text.",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            echo,
        )
    )

    # 3. read file
    reg.register(
        Tool(
            "read_file",
            "Read complete contents of a text file inside the workspace.",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative path to file"}},
                "required": ["path"],
            },
            read_file,
        )
    )

    # 4. list files
    reg.register(
        Tool(
            "list_files",
            "List files in a directory.",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
                "required": [],
            },
            list_files,
        )
    )

    # 5. glob
    reg.register(
        Tool(
            "glob",
            "Find files matching a glob pattern.",
            {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g. *.py)",
                    }
                },
                "required": ["pattern"],
            },
            glob,
        )
    )

    # 6. grep
    reg.register(
        Tool(
            "grep",
            "Search text patterns using regex.",
            {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "ignore_case": {"type": "boolean", "default": False},
                    "glob": {"type": "string"},
                },
                "required": ["pattern"],
            },
            grep,
        )
    )

    # 7. project tree
    reg.register(
        Tool(
            "project_tree",
            "View directory hierarchy tree.",
            {
                "type": "object",
                "properties": {"max_depth": {"type": "integer", "default": 3}},
                "required": [],
            },
            project_tree,
        )
    )

    # 8. web fetch
    reg.register(
        Tool(
            "web_fetch",
            "Fetch content of a web page and convert HTML to markdown.",
            {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            web_fetch,
        )
    )

    # 9. web search
    reg.register(
        Tool(
            "web_search",
            "Search the web via DuckDuckGo.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            web_search,
        )
    )

    # 10. file write
    reg.register(
        Tool(
            "file_write",
            "Write new content to a file. Overwrites existing.",
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["file_path", "content"],
            },
            file_write,
        )
    )

    # 11. file edit
    reg.register(
        Tool(
            "file_edit",
            "Atomically edit file by replacing an old string with a new string.",
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean", "default": False},
                },
                "required": ["file_path", "old_string", "new_string"],
            },
            file_edit,
        )
    )

    # 12. bash
    reg.register(
        Tool(
            "bash",
            "Run a bash shell command in the workspace.",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": 30},
                },
                "required": ["command"],
            },
            bash,
        )
    )

    # 13. git status
    reg.register(Tool("git_status", "Run git status in the workspace.", {}, _git_status))

    # 14. git diff
    reg.register(Tool("git_diff", "Run git diff in the workspace.", {}, _git_diff))

    # 15. ask user question
    reg.register(
        Tool(
            "ask_user_question",
            "Ask the user an interactive question.",
            {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["prompt", "options"],
            },
            _ask_user_question,
        )
    )

    return reg
