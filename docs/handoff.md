# JigAi — Handoff Document

> Last updated: 2026-03-09

---

## What It Is

**JigAi** (জিগাই — Bengali for "asking") is a tool-agnostic terminal notification system for AI coding agents. It detects when AI tools (Claude Code, Codex, Gemini CLI, Aider, OpenCode) are idle/waiting for input and:

1. Fires a macOS native notification
2. Pushes the event to a local WebSocket server
3. Mobile app (React Native) on the same LAN receives the notification

LAN-only, privacy-first, free and open-source.

- **Repo:** https://github.com/nafistiham/jigai (private)
- **Companion app:** https://github.com/nafistiham/jigai-app

---

## Current Status

| Phase | What | Status |
|-------|------|--------|
| Phase 1 | PTY proxy, idle detection, macOS notifications | ✅ Done |
| Phase 2 | FastAPI server, WebSocket, mDNS discovery, CLI | ✅ Done |
| Phase 3 | React Native mobile app (jigai-app repo) | 🔄 In progress |
| — | Daemon mode (`jigai daemon start/stop`) | ❌ Not started |
| — | Homebrew formula | ❌ Not started |
| — | PyPI publish | ❌ Ready to publish — pre-publish fixes done |

---

## Architecture

```
jigai watch claude
     ↓
PTY Proxy (pty_proxy.py)         — wraps any command transparently
     ↓
Idle Detector (detector.py)      — pattern match + timeout + cooldown
     ↓
Notifier (macos.py)              — osascript / terminal-notifier
     +
Server Push (client.py → app.py) — FastAPI REST + WebSocket broadcast
     ↓
Mobile App (jigai-app)           — React Native, mDNS auto-discovery
```

---

## Key Files

```
jigai/                           ← package root (pyproject.toml here)
jigai/jigai/
  cli.py                         ← Typer CLI (watch, server, config, patterns, sessions)
  config.py                      ← Pydantic config, ~/.jigai/config.yaml
  models.py                      ← IdleEvent, Session, shared types
  watcher/
    pty_proxy.py                 ← transparent PTY proxy
    detector.py                  ← idle detection (pattern + timeout + cooldown)
    patterns.py                  ← load defaults.yaml + user YAML
    watcher.py                   ← orchestrator
  notifier/
    macos.py                     ← osascript + terminal-notifier
  server/
    app.py                       ← FastAPI REST + WebSocket
    ws_manager.py                ← WebSocket connection manager
    discovery.py                 ← mDNS/Bonjour
    client.py                    ← HTTP push from watcher to server
  patterns/
    defaults.yaml                ← built-in patterns (Claude Code, Codex, Gemini, Aider, OpenCode)

tests/                           ← 72 tests across 4 files
```

---

## Pre-publish Fixes Applied (all committed)

These critical fixes were applied before PyPI publish:

1. Moved `patterns/defaults.yaml` → `jigai/patterns/defaults.yaml` (now included in pip install)
2. Fixed `only_when_away` early return that skipped server push
3. Added `os._exit(127)` after `os.execvp` failure
4. Fixed `on_spawn` callback so `session.pid` is set correctly
5. Fixed `_sanitize` backslash/quote ordering
6. Removed `setuptools-scm` from build-requires
7. Version strings use `__version__` consistently
8. All 65 ruff lint warnings fixed

---

## Dependencies

```
typer[all], fastapi, uvicorn[standard], websockets, zeroconf, pyyaml, rich, pydantic>=2.0
Dev: pytest, pytest-asyncio, pytest-cov, ruff, mypy
Python: >=3.10
```

## Setup on New Machine

```bash
cd JigAi/jigai
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
jigai watch claude
```

---

## Git Workflow

- Branches: `main` ← `develop` ← `feat/*` / `fix/*`
- Rebase only — no squash, no merge commits
- PyPI: Trusted Publishing via OIDC, GitHub environment named `release`

---

## What To Do Next

1. **Publish to PyPI** — run the GitHub Actions release workflow
2. **Phase 3: React Native mobile app** — see `jigai-app` repo for current state
3. **Daemon mode** — `jigai daemon start/stop` (not designed yet)
4. **Homebrew formula** — after PyPI is live
