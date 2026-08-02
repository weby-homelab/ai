from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pathspec
except ImportError:
    pathspec = None


TEXT_SUFFIXES = {
    ".py",
    ".pyi",
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".cfg",
    ".ini",
    ".env",
    ".sh",
    ".bash",
    ".zsh",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".sql",
    ".lock",
    ".gitignore",
}

MAX_READ_BYTES = 256 * 1024
DEFAULT_MAX_CHARS = 8000

DEFAULT_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)


@dataclass
class SkipPolicy:
    skip_dirs: frozenset[str] = DEFAULT_SKIP_DIRS
    gitignore: Any | None = None

    @classmethod
    def default(cls, gitignore: Any | None = None) -> SkipPolicy:
        return cls(gitignore=gitignore)


@dataclass
class ReadFileState:
    entries: dict[Path, tuple[int, int]] = field(default_factory=dict)

    def record(self, path: Path, content: str) -> None:
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return
        self.entries[path] = (mtime_ns, len(content))


def resolve_in_cwd(cwd: Path, user_path: str) -> Path:
    candidate = Path(cwd / user_path).resolve()
    cwd_resolved = cwd.resolve()
    try:
        candidate.relative_to(cwd_resolved)
    except ValueError as exc:
        raise ValueError(f"path escapes cwd: {user_path}") from exc
    return candidate


def ensure_text_file(path: Path) -> None:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return
    with path.open("rb") as f:
        if b"\x00" in f.read(1024):
            raise ValueError(f"binary file: {path.name}")


def ensure_within_size(path: Path, max_bytes: int = MAX_READ_BYTES) -> None:
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"file too large: {size} bytes > {max_bytes}; read a smaller file or use grep instead"
        )


def should_skip(rel_path: Path, policy: SkipPolicy) -> bool:
    if any(part in policy.skip_dirs for part in rel_path.parts):
        return True
    return bool(policy.gitignore is not None and policy.gitignore.match_file(str(rel_path)))


def truncate_output(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n[truncated {len(text) - max_chars} chars]"


def load_gitignore(cwd: Path) -> Any | None:
    if pathspec is None:
        return None
    gitignore = cwd / ".gitignore"
    if not gitignore.exists():
        return None
    try:
        lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)
    except Exception:
        return None


def ensure_read_before_edit(state: ReadFileState, path: Path) -> str | None:
    if path not in state.entries:
        return f"error: file has not been read yet. Read {path.name} first before editing."
    return None


def check_mtime_conflict(state: ReadFileState, path: Path) -> str | None:
    entry = state.entries.get(path)
    if entry is None:
        return None
    read_mtime_ns, _ = entry
    try:
        current_mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return None
    if current_mtime_ns > read_mtime_ns:
        return f"error: file was modified after read. Read {path.name} again before editing."
    return None


def apply_single_replace(
    content: str, old: str, new: str, replace_all: bool
) -> tuple[str | None, str | None]:
    if old == "":
        return None, "error: old_string must not be empty."
    if old == new:
        return None, "error: old_string and new_string are exactly the same."

    count = content.count(old)
    if count == 0:
        return None, "error: string to replace not found in file."
    if count > 1 and not replace_all:
        return None, (
            f"error: found {count} matches for old_string. "
            f"Use replace_all=True to replace all, or make old_string more specific."
        )

    if replace_all:
        return content.replace(old, new), None
    else:
        return content.replace(old, new, 1), None


def backup(cwd: Path, path: Path, old_content: str) -> Path | None:
    try:
        rel = path.resolve().relative_to(cwd.resolve())
    except ValueError:
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")[:-3] + "Z"
    backup_dir = cwd / ".agent" / "history" / rel
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / ts

    try:
        backup_path.write_text(old_content, encoding="utf-8")
    except OSError:
        return None
    return backup_path
