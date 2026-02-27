"""Tests for the idle detection engine."""

import time

from jigai.watcher.detector import Detector, strip_ansi
from jigai.watcher.patterns import PatternRegistry, ToolPattern, _compile_patterns

# ── Helpers ─────────────────────────────────────────────────


def make_registry(**kwargs) -> PatternRegistry:
    """Create a minimal test registry."""
    registry = PatternRegistry(
        timeout_seconds=kwargs.get("timeout", 5),
        cooldown_seconds=kwargs.get("cooldown", 0),
    )
    registry.tools["claude_code"] = ToolPattern(
        name="Claude Code",
        key="claude_code",
        patterns=_compile_patterns([
            r">>\s*$",
            r"(?i)waiting for.*input",
        ]),
    )
    registry.tools["codex"] = ToolPattern(
        name="Codex",
        key="codex",
        patterns=_compile_patterns([
            r"(?i)codex>\s*$",
        ]),
    )
    return registry


# ── Tests: strip_ansi ───────────────────────────────────────


class TestStripAnsi:
    def test_plain_text(self):
        assert strip_ansi("hello world") == "hello world"

    def test_color_codes(self):
        assert strip_ansi("\x1b[32mgreen\x1b[0m") == "green"

    def test_complex_sequences(self):
        assert strip_ansi("\x1b[1;34mBold Blue\x1b[0m text") == "Bold Blue text"

    def test_osc_sequences(self):
        assert strip_ansi("\x1b]0;Window Title\x07rest") == "rest"

    def test_empty_string(self):
        assert strip_ansi("") == ""


# ── Tests: Pattern Matching ─────────────────────────────────


class TestPatternMatching:
    def test_claude_prompt_match(self):
        registry = make_registry()
        tool = registry.tools["claude_code"]
        assert tool.matches(">> ")
        assert tool.matches(">>")

    def test_claude_waiting_match(self):
        registry = make_registry()
        tool = registry.tools["claude_code"]
        assert tool.matches("Waiting for your input")
        assert tool.matches("waiting for user input")

    def test_codex_prompt_match(self):
        registry = make_registry()
        tool = registry.tools["codex"]
        assert tool.matches("codex> ")
        assert tool.matches("Codex>")

    def test_no_match(self):
        registry = make_registry()
        tool = registry.tools["claude_code"]
        assert not tool.matches("Installing packages...")
        assert not tool.matches("Running tests...")

    def test_match_any(self):
        registry = make_registry()
        assert registry.match_any(">> ") == "claude_code"
        assert registry.match_any("codex> ") == "codex"
        assert registry.match_any("random output") is None


# ── Tests: Detector ─────────────────────────────────────────


class TestDetector:
    def test_pattern_detection(self):
        """Detector should fire on_idle when a pattern matches."""
        registry = make_registry(cooldown=0)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append((method, tool_key))

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line("Some normal output")
        detector.feed_line("More output here")
        detector.feed_line(">> ")

        assert len(events) == 1
        assert events[0] == ("pattern", "claude_code")

    def test_tool_hint_prioritized(self):
        """Detector with tool_hint should check that tool first."""
        registry = make_registry(cooldown=0)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(tool_key)

        detector = Detector(
            registry=registry, on_idle=on_idle, tool_hint="claude_code"
        )
        detector.feed_line(">> ")

        assert events == ["claude_code"]

    def test_cooldown_prevents_rapid_fire(self):
        """Detector should respect cooldown between notifications."""
        registry = make_registry(cooldown=10)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(tool_key)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line(">> ")
        detector.feed_line(">> ")
        detector.feed_line(">> ")

        # Only one event due to cooldown
        assert len(events) == 1

    def test_output_buffer(self):
        """Detector should maintain a buffer of recent output."""
        registry = make_registry(cooldown=0)
        events = []
        recent_lines = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(tool_key)
            recent_lines.extend(recent)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line("Line 1")
        detector.feed_line("Line 2")
        detector.feed_line("Line 3")
        detector.feed_line(">> ")

        assert "Line 1" in recent_lines
        assert "Line 2" in recent_lines
        assert "Line 3" in recent_lines

    def test_empty_lines_ignored(self):
        """Empty lines should not trigger detection."""
        registry = make_registry(cooldown=0)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(tool_key)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line("")
        detector.feed_line("   ")
        detector.feed_line("\n")

        assert len(events) == 0

    def test_ansi_stripped_before_matching(self):
        """ANSI codes should be stripped before pattern matching."""
        registry = make_registry(cooldown=0)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(tool_key)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line("\x1b[32m>> \x1b[0m")

        assert len(events) == 1
        assert events[0] == "claude_code"

    def test_redaction(self):
        """Sensitive data should be redacted in output buffer."""
        registry = make_registry(cooldown=0)
        recent_lines = []

        def on_idle(method, tool_key, idle_seconds, recent):
            recent_lines.extend(recent)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.set_redact_patterns([r"(?i)(token|password)=\S+"])

        detector.feed_line("Setting token=abc123secret")
        detector.feed_line("password=hunter2")
        detector.feed_line(">> ")

        # Check redacted content
        assert any("[REDACTED]" in line for line in recent_lines)
        assert not any("abc123secret" in line for line in recent_lines)
        assert not any("hunter2" in line for line in recent_lines)

    def test_get_recent_output(self):
        """get_recent_output should return last N lines."""
        registry = make_registry()
        detector = Detector(
            registry=registry, on_idle=lambda *args: None
        )

        for i in range(10):
            detector.feed_line(f"Line {i}")

        recent = detector.get_recent_output(3)
        assert len(recent) == 3
        assert recent[-1] == "Line 9"


# ── Tests: Timeout Detection ───────────────────────────────


class TestTimeoutDetection:
    def test_timeout_triggers_after_silence(self):
        """Timeout should trigger when no output for timeout_seconds."""
        registry = make_registry(timeout=1, cooldown=0)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(method)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line("Some output")

        # Manually set last_output_time to simulate passage of time
        detector.state.last_output_time = time.time() - 2

        detector.check_timeout()

        assert len(events) == 1
        assert events[0] == "timeout"

    def test_timeout_does_not_retrigger_while_idle(self):
        """Timeout should not re-trigger while already idle."""
        registry = make_registry(timeout=1, cooldown=0)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(method)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line("Some output")
        detector.state.last_output_time = time.time() - 2

        detector.check_timeout()
        detector.check_timeout()
        detector.check_timeout()

        # Only one event — is_idle prevents retrigger
        assert len(events) == 1

    def test_new_output_resets_idle(self):
        """New output should reset the idle state."""
        registry = make_registry(timeout=1, cooldown=0)
        events = []

        def on_idle(method, tool_key, idle_seconds, recent):
            events.append(method)

        detector = Detector(registry=registry, on_idle=on_idle)
        detector.feed_line("Some output")
        detector.state.last_output_time = time.time() - 2
        detector.check_timeout()

        assert len(events) == 1

        # New output resets idle
        detector.feed_line("New output arrived")
        assert detector.state.is_idle is False
