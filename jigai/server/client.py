"""HTTP client for pushing events from watchers to the JigAi server."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from jigai.models import IdleEvent


class ServerClient:
    """
    Lightweight HTTP client for pushing events to the JigAi server.

    Uses stdlib urllib to avoid adding httpx/requests as a dependency.
    """

    def __init__(self, base_url: str = "http://localhost:9384"):
        self.base_url = base_url.rstrip("/")

    def push_event(self, event: IdleEvent) -> bool:
        """Push an idle event to the server. Returns True on success."""
        url = f"{self.base_url}/api/events"
        data = json.dumps(event.model_dump(), default=str).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def register_session(
        self,
        session_id: str,
        tool_name: str,
        command: list[str],
        working_dir: str,
    ) -> bool:
        """Register a session with the server."""
        url = f"{self.base_url}/api/sessions"
        data = json.dumps({
            "session_id": session_id,
            "tool_name": tool_name,
            "command": command,
            "working_dir": working_dir,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def unregister_session(self, session_id: str) -> bool:
        """Unregister a session from the server."""
        url = f"{self.base_url}/api/sessions/{session_id}"
        req = urllib.request.Request(url, method="DELETE")

        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def is_server_running(self) -> bool:
        """Check if the server is reachable."""
        url = f"{self.base_url}/api/health"
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False
