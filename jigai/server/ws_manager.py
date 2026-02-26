"""WebSocket connection manager for broadcasting events to mobile clients."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections from mobile clients."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        # Add server timestamp
        data["server_time"] = datetime.now(timezone.utc).isoformat()
        message = json.dumps(data, default=str)

        # Send to all, remove dead connections
        dead: list[WebSocket] = []
        async with self._lock:
            for ws in self.active_connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self.active_connections.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)
