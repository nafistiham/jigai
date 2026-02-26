"""Watcher — orchestrates PTY proxy + detection engine for a single session."""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

from rich.console import Console

from jigai.config import JigAiConfig, load_config
from jigai.models import IdleEvent, Session, SessionStatus
from jigai.watcher.detector import Detector, strip_ansi
from jigai.watcher.patterns import PatternRegistry, detect_tool_from_command, load_patterns
from jigai.watcher.pty_proxy import PtyProxy

console = Console(stderr=True)


class Watcher:
    """
    Watches a single command via PTY proxy and detects idle state.

    Combines the PTY proxy (transparent I/O) with the detector (pattern + timeout)
    and emits notifications when idle is detected.
    """

    def __init__(
        self,
        command: list[str],
        tool_override: Optional[str] = None,
        config: Optional[JigAiConfig] = None,
        registry: Optional[PatternRegistry] = None,
        on_idle_event: Optional[callable] = None,
    ):
        self.command = command
        self.config = config or load_config()
        self.registry = registry or load_patterns()

        # Detect tool from command
        if tool_override:
            self.tool_key = tool_override
        else:
            self.tool_key = detect_tool_from_command(command, self.registry)

        tool_name = self.registry.get_tool_name(self.tool_key)

        # Create session
        self.session = Session(
            tool_name=tool_name,
            command=command,
            working_dir=os.getcwd(),
        )

        # External callback for idle events (e.g., server push)
        self._on_idle_event = on_idle_event

        # Line buffer for partial line accumulation
        self._line_buffer = ""

        # Create detector
        self.detector = Detector(
            registry=self.registry,
            on_idle=self._handle_idle,
            tool_hint=self.tool_key,
        )

        # Set redaction patterns
        self.detector.set_redact_patterns(self.config.notifications.redact_patterns)

        # Timeout checker thread
        self._timeout_thread: Optional[threading.Thread] = None
        self._running = False

    def _handle_output(self, data: bytes) -> None:
        """Called by PTY proxy with raw bytes from child stdout."""
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return

        # Accumulate into lines and feed to detector
        self._line_buffer += text
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            self.detector.feed_line(line)

        # Also check for prompt-like patterns in partial lines
        # (prompts often don't end with newline)
        if self._line_buffer.strip():
            self.detector.feed_line(self._line_buffer)

    def _handle_idle(
        self, method: str, tool_key: str, idle_seconds: float, recent_lines: list[str]
    ) -> None:
        """Called by detector when idle is detected."""
        tool_name = self.registry.get_tool_name(tool_key)

        # Get last N lines for notification
        n = self.config.notifications.output_lines
        last_output = "\n".join(recent_lines[-n:]) if recent_lines else ""

        # Create idle event
        event = IdleEvent(
            session_id=self.session.session_id,
            tool_name=tool_name,
            working_dir=self.session.working_dir,
            last_output=last_output,
            idle_seconds=idle_seconds,
            detection_method=method,
        )

        # Update session
        self.session.status = SessionStatus.IDLE
        self.session.last_output = last_output
        self.session.last_idle_event = event

        # Intentionally no terminal output — notifications are macOS/server only.

        # Fire macOS notification
        if self.config.notifications.macos:
            from jigai.notifier.macos import is_terminal_focused, notify_macos

            if self.config.notifications.only_when_away and is_terminal_focused():
                return  # User is looking at a terminal — skip notification

            subtitle = f"Session: {self.session.to_display_name()}"
            body = _last_meaningful_line(last_output) if last_output else ""
            if self.session.working_dir:
                dir_short = _shorten_path(self.session.working_dir)
                body = f"{body}\n{dir_short}" if body else dir_short

            notify_macos(
                title=f"{tool_name} is waiting",
                message=body,
                subtitle=subtitle,
                sound=self.config.notifications.sound,
                group=self.session.session_id if self.config.notifications.group_by_session else None,
            )

        # External callback (for server push)
        if self._on_idle_event:
            self._on_idle_event(event)

    def _handle_exit(self, exit_code: int) -> None:
        """Called when the child process exits."""
        self._running = False
        self.session.status = SessionStatus.STOPPED

    def _timeout_checker(self) -> None:
        """Background thread that periodically checks for timeout-based idle."""
        while self._running:
            time.sleep(1.0)
            if self._running:
                self.detector.check_timeout()

    def run(self) -> int:
        """Run the watcher. Blocks until the wrapped command exits."""
        display_name = self.session.to_display_name()
        console.print(
            f"[bold green]▶ [JigAi][/bold green] "
            f"Watching [cyan]{' '.join(self.command)}[/cyan] "
            f"as [yellow]{display_name}[/yellow]"
        )
        console.print(
            f"  [dim]Working dir: {self.session.working_dir}[/dim]"
        )
        console.print(
            f"  [dim]Timeout: {self.registry.timeout_seconds}s | "
            f"Cooldown: {self.registry.cooldown_seconds}s[/dim]"
        )
        console.print()

        # Start timeout checker thread
        self._running = True
        self._timeout_thread = threading.Thread(target=self._timeout_checker, daemon=True)
        self._timeout_thread.start()

        # Run PTY proxy (blocks)
        proxy = PtyProxy(
            command=self.command,
            on_output=self._handle_output,
            on_exit=self._handle_exit,
        )
        self.session.pid = proxy.child_pid

        try:
            exit_code = proxy.run()
        except KeyboardInterrupt:
            proxy.stop()
            exit_code = 130
        finally:
            self._running = False

        return exit_code


def _last_meaningful_line(text: str) -> str:
    """
    Return the last line with real readable content from a block of text.

    AI tool TUIs output lots of box-drawing separators and prompt chars.
    This skips those and strips decorative characters, returning only
    lines with actual human-readable text.
    """
    import re
    # Pure separator lines — skip entirely
    _SEPARATOR_RE = re.compile(r"^[\s\u2500-\u257F\-=_|*~\u2014\u2013]+$")
    # Decorative chars to strip from inside meaningful lines
    _DECOR_RE = re.compile(r"[\u2500-\u257F\u2580-\u259F\u25A0-\u25FF\u2600-\u26FF●✻⚡✓►▶⚠\-─━╭╮╰╯│]")
    # A line is only meaningful if it has 3+ consecutive letters after cleaning
    _HAS_ALPHA = re.compile(r"[a-zA-Z]{3,}")

    for line in reversed(text.split("\n")):
        stripped = line.strip()
        if not stripped or _SEPARATOR_RE.match(stripped):
            continue
        cleaned = _DECOR_RE.sub("", stripped).strip()
        if _HAS_ALPHA.search(cleaned):
            return cleaned
    return ""


def _shorten_path(path: str, max_len: int = 40) -> str:
    """Shorten a path for display, replacing home dir with ~."""
    home = os.path.expanduser("~")
    if path.startswith(home):
        path = "~" + path[len(home):]
    if len(path) > max_len:
        parts = path.split(os.sep)
        if len(parts) > 3:
            path = os.sep.join([parts[0], "...", *parts[-2:]])
    return path
