"""Pattern loading and management for idle detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jigai.config import BUILTIN_PATTERNS_FILE, USER_PATTERNS_FILE, load_yaml


@dataclass
class ToolPattern:
    """Compiled patterns for a single tool."""

    name: str
    key: str
    patterns: list[re.Pattern] = field(default_factory=list)

    def matches(self, line: str) -> bool:
        """Check if a line matches any of this tool's idle patterns."""
        return any(p.search(line) for p in self.patterns)


@dataclass
class PatternRegistry:
    """Registry of all loaded tool patterns."""

    tools: dict[str, ToolPattern] = field(default_factory=dict)
    timeout_seconds: int = 30
    cooldown_seconds: int = 5

    def match_any(self, line: str) -> str | None:
        """Check if a line matches any tool's idle pattern. Returns tool key or None."""
        for key, tool in self.tools.items():
            if tool.matches(line):
                return key
        return None

    def get_tool_name(self, key: str) -> str:
        """Get the display name for a tool key."""
        if key in self.tools:
            return self.tools[key].name
        return key


def _compile_patterns(raw_patterns: list[str]) -> list[re.Pattern]:
    """Compile a list of regex strings, skipping invalid ones."""
    compiled = []
    for pat_str in raw_patterns:
        try:
            compiled.append(re.compile(pat_str))
        except re.error:
            # Skip invalid patterns silently — log in future
            pass
    return compiled


def load_patterns() -> PatternRegistry:
    """Load patterns from built-in defaults and user overrides."""
    registry = PatternRegistry()

    # Load built-in patterns
    builtin = load_yaml(BUILTIN_PATTERNS_FILE)
    if "tools" in builtin:
        for key, tool_data in builtin["tools"].items():
            name = tool_data.get("name", key)
            raw = tool_data.get("idle_patterns", [])
            registry.tools[key] = ToolPattern(
                name=name,
                key=key,
                patterns=_compile_patterns(raw),
            )

    if "defaults" in builtin:
        registry.timeout_seconds = builtin["defaults"].get(
            "timeout_seconds", registry.timeout_seconds
        )
        registry.cooldown_seconds = builtin["defaults"].get(
            "cooldown_seconds", registry.cooldown_seconds
        )

    # Load user patterns (override/extend)
    user = load_yaml(USER_PATTERNS_FILE)
    if "custom_tools" in user:
        for key, tool_data in user["custom_tools"].items():
            name = tool_data.get("name", key)
            raw = tool_data.get("idle_patterns", [])
            registry.tools[key] = ToolPattern(
                name=name,
                key=key,
                patterns=_compile_patterns(raw),
            )

    if "overrides" in user:
        overrides = user["overrides"]
        if "timeout_seconds" in overrides:
            registry.timeout_seconds = overrides["timeout_seconds"]
        if "cooldown_seconds" in overrides:
            registry.cooldown_seconds = overrides["cooldown_seconds"]

    return registry


def detect_tool_from_command(command: list[str], registry: PatternRegistry) -> str:
    """Try to detect the tool name from the command being run."""
    if not command:
        return "unknown"

    cmd_str = " ".join(command).lower()

    # Map common command names to tool keys
    tool_hints: dict[str, list[str]] = {
        "claude_code": ["claude"],
        "codex": ["codex"],
        "gemini_cli": ["gemini"],
        "aider": ["aider"],
        "opencode": ["opencode"],
    }

    for tool_key, hints in tool_hints.items():
        if tool_key in registry.tools:
            for hint in hints:
                if hint in cmd_str:
                    return tool_key

    return "unknown"
