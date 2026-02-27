"""Detection engine — determines when a terminal session has gone idle."""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from jigai.watcher.patterns import PatternRegistry

# Regex to strip ANSI escape codes from terminal output
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?[@-~]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


@dataclass
class DetectorState:
    """Tracks the state of idle detection for a single session."""

    last_output_time: float = field(default_factory=time.time)
    last_idle_notification: float = 0.0
    output_buffer: deque = field(default_factory=lambda: deque(maxlen=50))
    is_idle: bool = False
    detected_tool: str | None = None


class Detector:
    """
    Idle detection engine.

    Combines pattern matching and timeout-based detection.
    Feeds terminal output line-by-line and emits idle events via callback.
    """

    def __init__(
        self,
        registry: PatternRegistry,
        on_idle: Callable[[str, str, float, list[str]], None],
        tool_hint: str | None = None,
    ):
        """
        Args:
            registry: Pattern registry with tool patterns loaded.
            on_idle: Callback(detection_method, tool_key, idle_seconds, recent_lines).
            tool_hint: Optional tool key hint from command detection.
        """
        self.registry = registry
        self.on_idle = on_idle
        self.tool_hint = tool_hint
        self.state = DetectorState()

        # Redaction patterns (loaded externally)
        self._redact_patterns: list[re.Pattern] = []

    def set_redact_patterns(self, patterns: list[str]) -> None:
        """Set patterns for redacting sensitive info from output."""
        self._redact_patterns = []
        for pat in patterns:
            try:
                self._redact_patterns.append(re.compile(pat))
            except re.error:
                pass

    def _redact(self, line: str) -> str:
        """Redact sensitive information from a line."""
        for pat in self._redact_patterns:
            line = pat.sub("[REDACTED]", line)
        return line

    def feed_line(self, raw_line: str) -> None:
        """
        Feed a single line of terminal output to the detector.

        This is called for every line of stdout from the watched process.
        """
        now = time.time()
        clean = strip_ansi(raw_line).strip()

        if not clean:
            return

        # Store in buffer (redacted)
        self.state.output_buffer.append(self._redact(clean))
        self.state.last_output_time = now
        self.state.is_idle = False

        # Try pattern matching
        # If we have a tool hint, check that tool first
        matched_tool = None
        if self.tool_hint and self.tool_hint in self.registry.tools:
            tool = self.registry.tools[self.tool_hint]
            if tool.matches(clean):
                matched_tool = self.tool_hint

        # If no match from hinted tool, try all tools
        if matched_tool is None:
            matched_tool = self.registry.match_any(clean)

        if matched_tool is not None:
            self._trigger_idle("pattern", matched_tool, now)

    def check_timeout(self) -> None:
        """
        Check if the timeout-based idle detection should trigger.

        Call this periodically (e.g., every second) from the watcher loop.
        """
        now = time.time()
        elapsed = now - self.state.last_output_time

        if elapsed >= self.registry.timeout_seconds and not self.state.is_idle:
            tool_key = self.tool_hint or "unknown"
            self._trigger_idle("timeout", tool_key, now)

    def _trigger_idle(self, method: str, tool_key: str, now: float) -> None:
        """Trigger an idle event if cooldown has passed."""
        cooldown = self.registry.cooldown_seconds
        if now - self.state.last_idle_notification < cooldown:
            return

        self.state.is_idle = True
        self.state.last_idle_notification = now
        self.state.detected_tool = tool_key

        idle_seconds = now - self.state.last_output_time
        recent = list(self.state.output_buffer)[-10:]  # Last 10 lines for context

        self.on_idle(method, tool_key, idle_seconds, recent)

    def get_recent_output(self, n: int = 3) -> list[str]:
        """Get the last N lines of (redacted) output."""
        return list(self.state.output_buffer)[-n:]
