"""Shared data models for JigAi."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Status of a watched session."""

    ACTIVE = "active"
    IDLE = "idle"
    STOPPED = "stopped"


class IdleEvent(BaseModel):
    """Emitted when a watched session goes idle."""

    session_id: str
    tool_name: str
    working_dir: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_output: str = ""
    idle_seconds: float = 0.0
    detection_method: str = "pattern"  # "pattern" | "timeout" | "combined"


class Session(BaseModel):
    """Represents a watched terminal session."""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    tool_name: str = "unknown"
    command: list[str] = Field(default_factory=list)
    working_dir: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: SessionStatus = SessionStatus.ACTIVE
    last_output: str = ""
    last_idle_event: IdleEvent | None = None
    pid: int | None = None

    def to_display_name(self) -> str:
        """Short display name for the session."""
        tool = self.tool_name or "session"
        return f"{tool}-{self.session_id}"
