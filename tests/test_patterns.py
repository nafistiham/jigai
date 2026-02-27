"""Tests for pattern loading and tool detection."""


from jigai.watcher.patterns import (
    PatternRegistry,
    ToolPattern,
    _compile_patterns,
    detect_tool_from_command,
    load_patterns,
)


class TestCompilePatterns:
    def test_valid_patterns(self):
        patterns = _compile_patterns([r"hello", r"\d+", r"^test$"])
        assert len(patterns) == 3

    def test_invalid_pattern_skipped(self):
        patterns = _compile_patterns([r"valid", r"[invalid", r"also_valid"])
        assert len(patterns) == 2

    def test_empty_list(self):
        assert _compile_patterns([]) == []


class TestLoadPatterns:
    def test_loads_builtin_patterns(self):
        registry = load_patterns()
        # Should have at least the built-in tools
        assert "claude_code" in registry.tools
        assert "codex" in registry.tools
        assert "gemini_cli" in registry.tools

    def test_builtin_patterns_compile(self):
        registry = load_patterns()
        for key, tool in registry.tools.items():
            assert len(tool.patterns) > 0, f"{key} has no compiled patterns"

    def test_defaults_loaded(self):
        registry = load_patterns()
        assert registry.timeout_seconds > 0
        assert registry.cooldown_seconds >= 0


class TestDetectToolFromCommand:
    def test_detect_claude(self):
        registry = load_patterns()
        assert detect_tool_from_command(["claude"], registry) == "claude_code"

    def test_detect_codex(self):
        registry = load_patterns()
        assert detect_tool_from_command(["codex"], registry) == "codex"

    def test_detect_gemini(self):
        registry = load_patterns()
        assert detect_tool_from_command(["gemini"], registry) == "gemini_cli"

    def test_detect_aider(self):
        registry = load_patterns()
        assert detect_tool_from_command(["aider"], registry) == "aider"

    def test_unknown_command(self):
        registry = load_patterns()
        assert detect_tool_from_command(["python", "my_script.py"], registry) == "unknown"

    def test_empty_command(self):
        registry = load_patterns()
        assert detect_tool_from_command([], registry) == "unknown"

    def test_command_with_args(self):
        registry = load_patterns()
        assert detect_tool_from_command(
            ["claude", "--model", "sonnet"], registry
        ) == "claude_code"


class TestPatternRegistry:
    def test_match_any_returns_first_match(self):
        registry = PatternRegistry()
        registry.tools["tool_a"] = ToolPattern(
            name="Tool A",
            key="tool_a",
            patterns=_compile_patterns([r"prompt_a>"]),
        )
        registry.tools["tool_b"] = ToolPattern(
            name="Tool B",
            key="tool_b",
            patterns=_compile_patterns([r"prompt_b>"]),
        )

        assert registry.match_any("prompt_a> ") == "tool_a"
        assert registry.match_any("prompt_b> ") == "tool_b"
        assert registry.match_any("random text") is None

    def test_get_tool_name(self):
        registry = PatternRegistry()
        registry.tools["test"] = ToolPattern(
            name="Test Tool", key="test", patterns=[]
        )
        assert registry.get_tool_name("test") == "Test Tool"
        assert registry.get_tool_name("nonexistent") == "nonexistent"
