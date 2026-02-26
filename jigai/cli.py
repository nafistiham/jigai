"""JigAi CLI — command-line interface."""

from __future__ import annotations

import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from jigai import __version__

app = typer.Typer(
    name="jigai",
    help="জিগাই — Tool-agnostic terminal notification system for AI coding agents.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]JigAi[/bold cyan] (জিগাই) v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """জিগাই — Know when your AI agent is waiting for you."""
    pass


# ── Watch Command ───────────────────────────────────────────


@app.command()
def watch(
    command: list[str] = typer.Argument(
        ...,
        help="Command to watch (e.g., 'claude', 'codex', 'python agent.py').",
    ),
    tool: Optional[str] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Override tool detection (e.g., 'claude_code', 'codex', 'my_agent').",
    ),
    no_notify: bool = typer.Option(
        False,
        "--no-notify",
        help="Disable macOS notifications.",
    ),
    no_server: bool = typer.Option(
        False,
        "--no-server",
        help="Don't push events to JigAi server.",
    ),
    timeout: Optional[int] = typer.Option(
        None,
        "--timeout",
        help="Override idle timeout in seconds.",
    ),
):
    """
    Watch a command and notify when it goes idle.

    Usage:
        jigai watch claude
        jigai watch -- codex
        jigai watch --tool my_agent -- python agent.py
    """
    from jigai.config import load_config
    from jigai.models import IdleEvent
    from jigai.server.client import ServerClient
    from jigai.watcher.patterns import load_patterns
    from jigai.watcher.watcher import Watcher

    config = load_config()
    registry = load_patterns()

    if no_notify:
        config.notifications.macos = False

    if timeout is not None:
        registry.timeout_seconds = timeout

    # Set up server push if available
    server_client = None
    if not no_server:
        client = ServerClient()
        if client.is_server_running():
            server_client = client
            console.print(
                "[dim]  Server: Connected to JigAi server[/dim]", style="green"
            )
        else:
            console.print(
                "[dim]  Server: Not running (use 'jigai server start' for mobile notifications)[/dim]"
            )

    def on_idle_event(event: IdleEvent) -> None:
        """Push idle events to the server."""
        if server_client:
            server_client.push_event(event)

    watcher = Watcher(
        command=command,
        tool_override=tool,
        config=config,
        registry=registry,
        on_idle_event=on_idle_event if server_client else None,
    )

    # Register session with server
    if server_client:
        server_client.register_session(
            session_id=watcher.session.session_id,
            tool_name=watcher.session.tool_name,
            command=command,
            working_dir=watcher.session.working_dir,
        )

    # Run (blocks until command exits)
    try:
        exit_code = watcher.run()
    finally:
        # Unregister session
        if server_client:
            server_client.unregister_session(watcher.session.session_id)

    raise typer.Exit(exit_code)


# ── Server Commands ─────────────────────────────────────────


server_app = typer.Typer(help="Manage the JigAi notification server.")
app.add_typer(server_app, name="server")


@server_app.command("start")
def server_start(
    port: int = typer.Option(9384, "--port", "-p", help="Server port."),
    host: str = typer.Option("0.0.0.0", "--host", help="Bind address."),
):
    """Start the JigAi notification server."""
    import uvicorn

    from jigai.server.app import create_app
    from jigai.server.discovery import get_local_ip

    local_ip = get_local_ip()
    console.print(f"\n[bold cyan]⚡ JigAi Server[/bold cyan]")
    console.print(f"  [dim]Local:   http://localhost:{port}[/dim]")
    console.print(f"  [dim]Network: http://{local_ip}:{port}[/dim]")
    console.print(f"  [dim]WS:      ws://{local_ip}:{port}/ws[/dim]")
    console.print()

    create_app(port=port)
    uvicorn.run(
        "jigai.server.app:app",
        host=host,
        port=port,
        log_level="warning",
    )


@server_app.command("status")
def server_status(
    port: int = typer.Option(9384, "--port", "-p", help="Server port."),
):
    """Check if the JigAi server is running."""
    from jigai.server.client import ServerClient

    client = ServerClient(f"http://localhost:{port}")
    if client.is_server_running():
        console.print("[green]✓[/green] JigAi server is running")
    else:
        console.print("[red]✗[/red] JigAi server is not running")
        console.print("  Start it with: [cyan]jigai server start[/cyan]")


# ── Config Commands ─────────────────────────────────────────


config_app = typer.Typer(help="Manage JigAi configuration.")
app.add_typer(config_app, name="config")


@config_app.command("init")
def config_init():
    """Create default configuration files."""
    from jigai.config import (
        CONFIG_FILE,
        USER_PATTERNS_FILE,
        ensure_dirs,
        save_default_config,
    )

    ensure_dirs()

    if CONFIG_FILE.exists():
        console.print(f"[yellow]Config already exists:[/yellow] {CONFIG_FILE}")
    else:
        path = save_default_config()
        console.print(f"[green]✓[/green] Created config: {path}")

    if not USER_PATTERNS_FILE.exists():
        # Create example user patterns file
        example = (
            "# JigAi — Custom tool patterns\n"
            "# Add your own tools here.\n"
            "#\n"
            "# custom_tools:\n"
            "#   my_agent:\n"
            '#     name: "My Custom Agent"\n'
            "#     idle_patterns:\n"
            "#       - 'READY>'\n"
            "#       - 'awaiting instruction'\n"
            "#\n"
            "# overrides:\n"
            "#   timeout_seconds: 45\n"
        )
        USER_PATTERNS_FILE.write_text(example)
        console.print(f"[green]✓[/green] Created patterns: {USER_PATTERNS_FILE}")
    else:
        console.print(
            f"[yellow]Patterns already exists:[/yellow] {USER_PATTERNS_FILE}"
        )


@config_app.command("show")
def config_show():
    """Show current configuration."""
    from jigai.config import load_config

    config = load_config()
    console.print_json(data=config.model_dump())


@config_app.command("test")
def config_test(
    line: str = typer.Argument(..., help="A line of terminal output to test."),
):
    """Test if a line of output matches any idle pattern."""
    from jigai.watcher.detector import strip_ansi
    from jigai.watcher.patterns import load_patterns

    registry = load_patterns()
    clean = strip_ansi(line).strip()

    console.print(f"Testing: [cyan]{clean}[/cyan]\n")

    matched = False
    for key, tool in registry.tools.items():
        if tool.matches(clean):
            console.print(f"  [green]✓ MATCH[/green] → {tool.name} ({key})")
            matched = True

    if not matched:
        console.print("  [yellow]No pattern matched.[/yellow]")
        console.print(
            f"  [dim]Timeout fallback would trigger after "
            f"{registry.timeout_seconds}s of silence.[/dim]"
        )


# ── Info Commands ───────────────────────────────────────────


@app.command()
def patterns():
    """Show all loaded idle detection patterns."""
    from jigai.watcher.patterns import load_patterns

    registry = load_patterns()

    table = Table(title="JigAi — Loaded Patterns")
    table.add_column("Tool", style="cyan")
    table.add_column("Key", style="dim")
    table.add_column("Patterns", style="green")

    for key, tool in registry.tools.items():
        pat_list = "\n".join(p.pattern for p in tool.patterns)
        table.add_row(tool.name, key, pat_list)

    console.print(table)
    console.print(
        f"\n[dim]Timeout: {registry.timeout_seconds}s | "
        f"Cooldown: {registry.cooldown_seconds}s[/dim]"
    )


@app.command()
def sessions(
    port: int = typer.Option(9384, "--port", "-p", help="Server port."),
):
    """List active watched sessions (requires server running)."""
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/api/sessions", timeout=2
        ) as resp:
            data = json.loads(resp.read())
    except Exception:
        console.print("[red]✗[/red] Cannot connect to server.")
        console.print("  Start it with: [cyan]jigai server start[/cyan]")
        raise typer.Exit(1)

    sess_list = data.get("sessions", [])

    if not sess_list:
        console.print("[dim]No active sessions.[/dim]")
        return

    table = Table(title="Active Sessions")
    table.add_column("Session ID", style="yellow")
    table.add_column("Tool", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Working Dir", style="dim")

    for s in sess_list:
        status_style = "green" if s.get("status") == "active" else "yellow"
        table.add_row(
            s.get("session_id", "?"),
            s.get("tool_name", "?"),
            f"[{status_style}]{s.get('status', '?')}[/{status_style}]",
            s.get("working_dir", ""),
        )

    console.print(table)


if __name__ == "__main__":
    app()
