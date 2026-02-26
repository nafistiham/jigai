"""Configuration management for JigAi."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


JIGAI_DIR = Path.home() / ".jigai"
CONFIG_FILE = JIGAI_DIR / "config.yaml"
USER_PATTERNS_FILE = JIGAI_DIR / "patterns.yaml"
DAEMON_PID_FILE = JIGAI_DIR / "daemon.pid"
LOG_DIR = JIGAI_DIR / "logs"

# Bundled defaults shipped with the package
BUILTIN_PATTERNS_FILE = Path(__file__).parent.parent / "patterns" / "defaults.yaml"


class NotificationConfig(BaseModel):
    """Notification settings."""

    macos: bool = True
    only_when_away: bool = False  # Skip notification if a terminal is the focused window
    sound: str = "Ping"
    group_by_session: bool = True
    show_last_output: bool = True
    output_lines: int = 3
    redact_patterns: list[str] = Field(
        default_factory=lambda: [r"(?i)(token|password|secret|key|api_key)=\S+"]
    )


class DetectionConfig(BaseModel):
    """Detection engine settings."""

    timeout_seconds: int = 30
    cooldown_seconds: int = 5


class ServerConfig(BaseModel):
    """Server settings."""

    port: int = 9384
    bind: str = "0.0.0.0"


class SessionConfig(BaseModel):
    """Session display settings."""

    show_working_dir: bool = True
    show_last_output: bool = True


class JigAiConfig(BaseModel):
    """Root configuration model."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    sessions: SessionConfig = Field(default_factory=SessionConfig)


def ensure_dirs() -> None:
    """Create JigAi directories if they don't exist."""
    JIGAI_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> JigAiConfig:
    """Load configuration from ~/.jigai/config.yaml, falling back to defaults."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        return JigAiConfig(**raw)
    return JigAiConfig()


def save_default_config() -> Path:
    """Write default config to ~/.jigai/config.yaml."""
    ensure_dirs()
    config = JigAiConfig()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)
    return CONFIG_FILE


def load_yaml(path: Path) -> dict[str, Any]:
    """Safely load a YAML file, returning empty dict on failure."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}
