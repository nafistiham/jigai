"""Tests for watcher utility functions and macOS notifier helpers."""

from unittest.mock import patch

from jigai.models import IdleEvent
from jigai.notifier.macos import _sanitize, is_terminal_focused
from jigai.watcher.watcher import _last_meaningful_line, _shorten_path

# ── Tests: _last_meaningful_line ────────────────────────────


class TestLastMeaningfulLine:
    def test_plain_text(self):
        assert _last_meaningful_line("hello world") == "hello world"

    def test_returns_last_real_line(self):
        text = "Running tests\nAll tests passed\n"
        assert _last_meaningful_line(text) == "All tests passed"

    def test_skips_separator_lines(self):
        text = "Real content here\n─────────────────"
        assert _last_meaningful_line(text) == "Real content here"

    def test_skips_box_drawing_separators(self):
        text = "Useful message\n╭──────────────────╮\n│                  │"
        assert _last_meaningful_line(text) == "Useful message"

    def test_skips_dash_separator(self):
        text = "Some output\n-----------------------------------"
        assert _last_meaningful_line(text) == "Some output"

    def test_strips_decorative_chars(self):
        # Line with decorative chars but real text
        text = "✻ Thinking…"
        result = _last_meaningful_line(text)
        assert "Thinking" in result

    def test_empty_string(self):
        assert _last_meaningful_line("") == ""

    def test_only_separators(self):
        text = "─────────\n==========\n----------"
        assert _last_meaningful_line(text) == ""

    def test_requires_three_consecutive_letters(self):
        # Single or two letters don't count as meaningful
        text = "─────────\nok\n─────────"
        assert _last_meaningful_line(text) == ""

    def test_claude_code_tui_output(self):
        # Simulate typical Claude Code output block
        text = (
            "╭─ ✻ Thinking… ──────────────────╮\n"
            "│                                 │\n"
            "╰─────────────────────────────────╯\n"
            "Here is my plan for the refactor"
        )
        result = _last_meaningful_line(text)
        assert "plan" in result or "refactor" in result

    def test_strips_leading_trailing_underscore_decoration(self):
        # Lines like "___ Tool Output ___" should have edge underscores removed
        text = "___ Tool Output ___"
        result = _last_meaningful_line(text)
        assert result == "Tool Output"
        assert "_" not in result

    def test_strips_long_underscore_run_at_edges(self):
        # Very long underscore runs (e.g. pytest separator) should be stripped
        text = "Some output\n___________ Running tests ___________"
        result = _last_meaningful_line(text)
        assert "Running tests" in result
        assert "_" not in result

    def test_preserves_python_dunder_names(self):
        # __init__.py has only 2 underscores — should NOT be stripped
        text = "__init__.py"
        result = _last_meaningful_line(text)
        assert "init" in result

    def test_preserves_underscore_in_middle_of_word(self):
        # Underscores inside a word (e.g. tool names) are kept
        text = "Running tool: computer_use"
        result = _last_meaningful_line(text)
        assert "computer_use" in result

    def test_only_underscore_line_is_skipped(self):
        # A line of pure underscores should be skipped entirely
        text = "Useful content\n___________________________"
        result = _last_meaningful_line(text)
        assert result == "Useful content"


# ── Tests: IdleEvent.notification_body ──────────────────────


class TestIdleEventNotificationBody:
    def test_notification_body_field_exists(self):
        event = IdleEvent(
            session_id="abc123",
            tool_name="Claude Code",
            working_dir="/tmp",
        )
        assert hasattr(event, "notification_body")
        assert event.notification_body == ""

    def test_notification_body_can_be_set(self):
        event = IdleEvent(
            session_id="abc123",
            tool_name="Claude Code",
            working_dir="/tmp",
            notification_body="Waiting for input",
        )
        assert event.notification_body == "Waiting for input"


# ── Tests: _shorten_path ────────────────────────────────────


class TestShortenPath:
    def test_replaces_home_with_tilde(self):
        import os
        home = os.path.expanduser("~")
        result = _shorten_path(f"{home}/projects/foo")
        assert result.startswith("~")
        assert home not in result

    def test_short_path_unchanged(self):
        result = _shorten_path("/tmp/foo")
        assert result == "/tmp/foo"

    def test_long_path_truncated(self):
        path = "/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v"
        result = _shorten_path(path, max_len=20)
        assert "..." in result
        assert len(result) <= len(path)

    def test_truncated_path_keeps_last_two_parts(self):
        path = "/a/b/c/d/this_project/src"
        result = _shorten_path(path, max_len=10)
        assert "this_project" in result or "src" in result


# ── Tests: is_terminal_focused ──────────────────────────────


class TestIsTerminalFocused:
    def test_terminal_app_returns_true(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "iTerm2\n"
            assert is_terminal_focused() is True

    def test_non_terminal_app_returns_false(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "Safari\n"
            assert is_terminal_focused() is False

    def test_timeout_returns_false(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 2)):
            assert is_terminal_focused() is False

    def test_osascript_not_found_returns_false(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert is_terminal_focused() is False

    def test_warp_terminal_returns_true(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "Warp\n"
            assert is_terminal_focused() is True

    def test_ghostty_returns_true(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "Ghostty\n"
            assert is_terminal_focused() is True


# ── Tests: _sanitize ────────────────────────────────────────


class TestSanitize:
    def test_plain_text_unchanged(self):
        assert _sanitize("hello world") == "hello world"

    def test_escapes_backslash_before_quote(self):
        # backslash first, then quote — key order test
        result = _sanitize('say "hello"')
        assert result == 'say \\"hello\\"'

    def test_backslash_not_doubled_after_quote_escape(self):
        # The old bug: escape " → \", then escape \ → \\, giving \\"
        # Correct: backslash → \\, then " → \", giving \\"hello\\"
        result = _sanitize('"')
        assert result == '\\"'

    def test_existing_backslash_doubled(self):
        result = _sanitize("path\\to\\file")
        assert result == "path\\\\to\\\\file"

    def test_newline_replaced(self):
        result = _sanitize("line1\nline2")
        assert result == "line1 ⏎ line2"

    def test_backslash_then_quote(self):
        # Input: \" — should become \\\"
        result = _sanitize('\\"')
        assert result == '\\\\\\"'
