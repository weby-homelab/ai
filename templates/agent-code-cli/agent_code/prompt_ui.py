from __future__ import annotations

import difflib

import typer
from rich.console import Console

console = Console()


def render_diff(old: str, new: str, path: str) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    colored = []
    for line in diff_lines:
        line = line.rstrip()
        if line.startswith(("---", "+++")):
            colored.append(f"[bold]{line}[/bold]")
        elif line.startswith("-"):
            colored.append(f"[red]{line}[/red]")
        elif line.startswith("+"):
            colored.append(f"[green]{line}[/green]")
        elif line.startswith("@@"):
            colored.append(f"[cyan]{line}[/cyan]")
        else:
            colored.append(line)
    return "\n".join(colored)


def confirm_edit(path: str) -> bool:
    return typer.confirm(f"Apply this edit to {path}?", default=False)


def confirm_command(command: str) -> bool:
    console.print(
        f"\n[bold yellow]! Requesting command execution:[/bold yellow] [bold cyan]{command}[/bold cyan]"
    )
    return typer.confirm("Do you want to run this command?", default=False)


def confirm_tool_use(tool_name: str, detail: str) -> bool:
    return typer.confirm(f"Allow {tool_name}: {detail}?", default=False)


def prompt_single_choice(question: str, labels: list[str]) -> str | None:
    console.print(f"\n[bold yellow]? {question}[/bold yellow]")
    for i, label in enumerate(labels, 1):
        console.print(f"  {i}. {label}")
    console.print("  0. [dim]Skip / Other[/dim]")

    try:
        choice = typer.prompt("Choice", default="0")
        idx = int(choice)
        if 1 <= idx <= len(labels):
            return labels[idx - 1]
        return None
    except (ValueError, TypeError):
        return None
