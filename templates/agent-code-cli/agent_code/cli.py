from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .agent import build_system_prompt, run_agent
from .model import create_provider
from .session import Session
from .tools import default_tools

console = Console()
app = typer.Typer(add_completion=False)


def render_header(cwd: Path, provider: str, model: str, base_url: str | None) -> None:
    console.print("[bold cyan]🤖 AI-HomeLab Agent CLI[/bold cyan]")
    console.print(f"[dim]Workspace CWD: {cwd}[/dim]")
    console.print(f"[dim]Provider: {provider} | Model: {model}[/dim]")
    if base_url:
        console.print(f"[dim]Base URL: {base_url}[/dim]")
    console.print()


def run_once(
    prompt: str,
    cwd: Path,
    provider_name: str,
    model: str,
    base_url: str | None,
    max_steps: int,
    permission_mode: str,
    session: Session | None = None,
    system_prompt: str | None = None,
) -> None:
    if session:
        suffix = " (resumed)" if session.resumed else ""
        console.print(f"[dim]session: {session.session_id}{suffix}[/dim]")

    try:
        provider = create_provider(provider_name, model, base_url)
    except Exception as e:
        console.print(f"[red]Error creating provider: {e}[/red]")
        raise typer.Exit(code=1)

    run_agent(
        prompt,
        provider,
        default_tools(),
        max_steps=max_steps,
        cwd=cwd,
        permission_mode=permission_mode,
        session=session,
        system_prompt=system_prompt,
    )


@app.callback(invoke_without_command=True)
def main_command(
    prompt: str = typer.Argument("", help="Промпт для ШІ-агента. Якщо порожній, запускає REPL."),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", "-C", help="Робоча директорія."),
    provider: str = typer.Option(
        "ollama", "--provider", help="Провайдер моделей: ollama, anthropic, mock."
    ),
    model: str = typer.Option("gemma3:4b", "--model", help="Назва моделі."),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Кастомна адреса хоста (напр. URL Ollama)."
    ),
    max_steps: int = typer.Option(
        10, "--max-steps", help="Максимальна кількість кроків у Agent Loop."
    ),
    permission_mode: str = typer.Option(
        "default",
        "--permission-mode",
        help="Режим доступу: default, acceptEdits, plan.",
    ),
    resume: str | None = typer.Option(None, "--resume", help="Відновити сесію за ID."),
    continue_: bool = typer.Option(False, "--continue", "-c", help="Продовжити останню сесію."),
) -> None:
    resolved_cwd = cwd.resolve()
    session = None

    if continue_:
        session = Session.load_latest(resolved_cwd)
        if session is None:
            console.print(
                "[red]Історія сесій не знайдена, неможливо продовжити (--continue).[/red]"
            )
            raise typer.Exit(code=1)
    elif resume:
        session = Session.load_id(resolved_cwd, resume)
        if session is None:
            console.print(f"[red]Сесія з ID {resume} не знайдена.[/red]")
            raise typer.Exit(code=1)

    system_prompt = build_system_prompt(resolved_cwd)

    if prompt.strip():
        # Single prompt run mode
        render_header(resolved_cwd, provider, model, base_url)
        if session is None:
            session = Session.create(resolved_cwd)
        run_once(
            prompt.strip(),
            resolved_cwd,
            provider,
            model,
            base_url,
            max_steps,
            permission_mode,
            session=session,
            system_prompt=system_prompt,
        )
        return

    # Interactive REPL mode
    render_header(resolved_cwd, provider, model, base_url)
    if session is None:
        session = Session.create(resolved_cwd)

    console.print(f"[green]Session ID: {session.session_id}[/green]")
    console.print("Введіть ваше запитання або інструкцію для кодування.")
    console.print("Для виходу введіть [bold red]/exit[/bold red] або натисніть Ctrl+D.\n")

    while True:
        try:
            line = input("agent-code > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\nBye.")
            break

        if not line:
            continue

        if line == "/exit":
            console.print("Bye.")
            break

        run_once(
            line,
            resolved_cwd,
            provider,
            model,
            base_url,
            max_steps,
            permission_mode,
            session=session,
            system_prompt=system_prompt,
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
