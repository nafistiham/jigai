"""FastAPI server — receives idle events and broadcasts to mobile clients."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from jigai.models import IdleEvent, Session, SessionStatus
from jigai.server.discovery import ServiceBroadcaster
from jigai.server.ws_manager import ConnectionManager


# Global state
manager = ConnectionManager()
broadcaster = ServiceBroadcaster()
sessions: dict[str, dict[str, Any]] = {}
event_history: list[dict[str, Any]] = []
MAX_HISTORY = 100


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop mDNS broadcasting with the server lifecycle."""
    port = app.state.port if hasattr(app.state, "port") else 9384
    broadcaster.port = port
    broadcaster.start()
    yield
    broadcaster.stop()


app = FastAPI(
    title="JigAi Server",
    description="Terminal notification hub for AI coding agents",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow CORS for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Endpoints ──────────────────────────────────────────


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "clients": manager.client_count,
        "sessions": len(sessions),
    }


@app.get("/api/sessions")
async def list_sessions():
    """List all active watched sessions."""
    return {"sessions": list(sessions.values())}


@app.get("/api/events")
async def list_events(limit: int = 20):
    """List recent idle events."""
    return {"events": event_history[-limit:]}


class IdleEventRequest(BaseModel):
    """Incoming idle event from a watcher."""

    session_id: str
    tool_name: str
    working_dir: str = ""
    last_output: str = ""
    idle_seconds: float = 0.0
    detection_method: str = "pattern"


@app.post("/api/events")
async def receive_event(event: IdleEventRequest):
    """Receive an idle event from a watcher and broadcast to clients."""
    event_data = {
        "type": "idle_detected",
        "session_id": event.session_id,
        "tool_name": event.tool_name,
        "working_dir": event.working_dir,
        "last_output": event.last_output,
        "idle_seconds": event.idle_seconds,
        "detection_method": event.detection_method,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Update session registry
    sessions[event.session_id] = {
        "session_id": event.session_id,
        "tool_name": event.tool_name,
        "working_dir": event.working_dir,
        "status": "idle",
        "last_event": event_data,
    }

    # Store in history
    event_history.append(event_data)
    if len(event_history) > MAX_HISTORY:
        event_history.pop(0)

    # Broadcast to all WebSocket clients
    await manager.broadcast(event_data)

    return {"status": "ok", "clients_notified": manager.client_count}


class SessionRegisterRequest(BaseModel):
    """Register a new watched session."""

    session_id: str
    tool_name: str
    command: list[str] = []
    working_dir: str = ""


@app.post("/api/sessions")
async def register_session(req: SessionRegisterRequest):
    """Register a new watched session."""
    sessions[req.session_id] = {
        "session_id": req.session_id,
        "tool_name": req.tool_name,
        "command": req.command,
        "working_dir": req.working_dir,
        "status": "active",
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }

    await manager.broadcast({
        "type": "session_started",
        "session_id": req.session_id,
        "tool_name": req.tool_name,
        "working_dir": req.working_dir,
    })

    return {"status": "ok"}


@app.delete("/api/sessions/{session_id}")
async def unregister_session(session_id: str):
    """Remove a watched session."""
    if session_id in sessions:
        del sessions[session_id]

    await manager.broadcast({
        "type": "session_stopped",
        "session_id": session_id,
    })

    return {"status": "ok"}


# ── WebSocket Endpoint ──────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for mobile clients."""
    await manager.connect(websocket)

    # Send current state on connect
    try:
        await websocket.send_json({
            "type": "connected",
            "sessions": list(sessions.values()),
            "server_version": "0.1.0",
        })

        # Keep connection alive
        while True:
            try:
                # Wait for messages (ping/pong, or future commands)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket)


def create_app(port: int = 9384) -> FastAPI:
    """Create the app with the given port for mDNS."""
    app.state.port = port
    return app
