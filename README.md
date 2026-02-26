# JigAi (জিগাই)

<p align="center">
  <strong>জিগাই</strong> — Bangla for <em>"asking"</em> — Know when your AI agent is waiting for you.
</p>

<p align="center">
  <a href="https://pypi.org/project/jigai"><img src="https://img.shields.io/pypi/v/jigai?color=blue&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/jigai"><img src="https://img.shields.io/pypi/pyversions/jigai" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey" alt="Platform">
  <a href="https://github.com/nafistiham/jigai/actions"><img src="https://github.com/nafistiham/jigai/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

---

A **tool-agnostic** terminal notification system that watches AI coding agents — Claude Code, Codex, Gemini CLI, Aider, or any custom tool — and notifies you via **macOS notifications** and optionally your **phone over LAN** the moment they go idle and need your input.

**No hooks. No per-tool config. Just wrap your command and go.**

```bash
pip install jigai
jigai watch claude
```

---

## The Problem

You kick off Claude Code on a big refactor, switch to your browser to research something, and come back 20 minutes later to find it asked a clarifying question in the first 30 seconds. You just wasted 20 minutes.

Every AI coding tool has this problem. None of them have a universal solution. Hook-based approaches require per-tool configuration that breaks across versions. Cloud notification services require accounts, subscriptions, or trusting a third party with your terminal output.

**JigAi** fixes this with a single transparent PTY proxy that watches any terminal output, detects idle patterns, and notifies you — locally, privately, instantly.

---

## How It Works

JigAi wraps your AI tool in a **PTY (pseudo-terminal) proxy**. Your tool runs exactly as normal — same colors, same interactivity, same behavior. JigAi intercepts the output stream silently:

```
You type:  jigai watch claude
           │
           ▼
    ┌──────────────────┐
    │   JigAi Watcher  │  ← sits here transparently
    │   (PTY proxy)    │
    └────────┬─────────┘
             │ passes all I/O through unchanged
             ▼
    ┌──────────────────┐
    │   Claude Code    │  ← behaves exactly as if launched directly
    └──────────────────┘
```

When idle is detected (via pattern match or timeout), JigAi fires:
1. A **macOS notification** with the last meaningful output line
2. A **WebSocket push** to the JigAi server (if running)
3. Your phone receives the notification via the LAN server *(mobile app coming in v0.2)*

---

## Quick Start

### 1. Install

```bash
pip install jigai
```

For richer notifications (banner popups instead of silent NC delivery):

```bash
brew install terminal-notifier
```

> See [Notification Setup](#notification-setup) for macOS configuration steps.

### 2. Watch a tool

```bash
# Claude Code
jigai watch claude

# OpenAI Codex CLI
jigai watch codex

# Gemini CLI
jigai watch gemini

# Aider
jigai watch aider

# Any arbitrary command
jigai watch -- python my_agent.py

# Override tool detection (for custom prompts)
jigai watch --tool my_agent -- python agent.py
```

### 3. (Optional) Start the server for LAN mobile push

```bash
# Terminal 1 — keep the server running
jigai server start

# Terminal 2 — watch your tool as normal
jigai watch claude
```

That's it. When Claude Code goes idle, you get notified.

---

## Supported Tools

| Tool | Detection Method | Status |
|------|-----------------|--------|
| Claude Code | Pattern + timeout | Built-in |
| OpenAI Codex CLI | Pattern + timeout | Built-in |
| Gemini CLI | Pattern + timeout | Built-in |
| Aider | Pattern + timeout | Built-in |
| OpenCode | Pattern + timeout | Built-in |
| Any custom tool | User-defined regex | Via `~/.jigai/patterns.yaml` |

JigAi also has a **timeout fallback**: if no output is received for `timeout_seconds` (default: 30s), it fires regardless of pattern matching. This means it works with any tool, even ones not in the list above.

---

## Notification Setup

JigAi uses two delivery mechanisms. Both are attempted in order:

### 1. `terminal-notifier` (Recommended — banner popups)

Install via Homebrew:

```bash
brew install terminal-notifier
```

Then configure macOS to show banners:

1. Open **System Settings → Notifications → terminal-notifier**
2. Enable **Allow Notifications**
3. Check **Desktop** (required for banner popups)
4. Set **Alert Style** to **Persistent** (stays until dismissed) or **Temporary** (auto-dismisses)
5. Enable **Play sound for notification**

### 2. `osascript` (Fallback — no installation required)

If `terminal-notifier` is not installed, JigAi falls back to macOS's built-in `osascript`. Notifications will appear in **Notification Center** but may not show as banner popups, depending on your macOS version and Script Editor's notification settings.

> **Recommendation:** Install `terminal-notifier` for the best experience.

---

## Known Issues and Caveats

Read this section before filing a bug report — most common issues are documented here.

### Focus Mode blocks banner notifications

**Symptom:** Notifications appear in Notification Center but the banner popup never shows, even with correct settings.

**Cause:** macOS Focus Mode (Do Not Disturb, Work, Personal, etc.) silences notification banners from apps not explicitly allowed.

**Fix:**
1. Open **System Settings → Focus**
2. Select your active Focus profile
3. Under **Allowed Notifications → Apps**, add **terminal-notifier**

This is a one-time setup per Focus profile. Once allowed, banners will appear even when Focus is active.

---

### `terminal-notifier` on macOS Sequoia (15.x)

**Symptom:** Notifications appear in Notification Center but never pop as banners, or `terminal-notifier` produces no output at all.

**Cause:** `terminal-notifier` has known compatibility issues on macOS Sequoia 15, particularly on M-series chips ([issue #312](https://github.com/julienXX/terminal-notifier/issues/312)). The binary is not updated for the newer UserNotifications framework in Sequoia.

**Workarounds:**
- Try resetting the notification registration:
  ```bash
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user
  ```
  Then re-open System Settings → Notifications → terminal-notifier and re-enable.
- If still broken, notifications will still land in Notification Center via the `osascript` fallback — you just won't get the popup banner.
- A native Swift notification backend is planned for v0.2 that will resolve this permanently.

---

### Display mirroring / screen sharing

**Symptom:** Notifications don't show on the desktop while screen sharing or mirroring.

**Fix:** System Settings → Notifications → enable **"Allow notifications when mirroring or sharing the display"**

---

### Notifications fire while you're at the terminal

By default, JigAi will fire a notification even if you're actively looking at the terminal. This is intentional — the sound alone can be useful as a cue.

To suppress notifications when a terminal window is focused:

```yaml
# ~/.jigai/config.yaml
notifications:
  only_when_away: true
```

JigAi checks the frontmost macOS application. If it's Terminal, iTerm2, Warp, Ghostty, Alacritty, Kitty, or similar, the notification is skipped. Supported terminal app names are: `terminal`, `iterm2`, `warp`, `hyper`, `alacritty`, `kitty`, `ghostty`, `tabby`, `rio`.

---

### Idle fires too early or too often

**Cause:** Pattern matching may trigger on output lines that superficially resemble idle prompts, especially for tools with rich TUI output.

**Fix:** Adjust the cooldown (minimum gap between notifications) and timeout:

```yaml
# ~/.jigai/config.yaml
detection:
  timeout_seconds: 45   # how long to wait before timeout-based idle
  cooldown_seconds: 10  # minimum seconds between notifications
```

Or test which lines trigger detection:

```bash
jigai config test "some terminal output line"
```

---

### Pattern detection for Claude Code

Claude Code renders a rich TUI with box-drawing characters and animated spinners. JigAi strips all ANSI codes and decorative Unicode before matching, and the idle prompt (`>`) is the primary pattern matched.

If you find detection is unreliable, set a longer timeout:

```bash
jigai watch --timeout 60 claude
```

---

### iOS / Android mobile notifications (LAN)

The mobile app is planned for **v0.2**. Currently, `jigai server start` runs a WebSocket server that a future React Native app will connect to.

iOS note: iOS aggressively terminates background WebSocket connections. When the mobile app is built, foreground/background behavior will be documented. Users on iOS may want to keep the app in the foreground or use a notification relay for reliable background delivery.

---

## Configuration

### Config file: `~/.jigai/config.yaml`

Initialize with defaults:

```bash
jigai config init
```

Full reference:

```yaml
server:
  port: 9384          # LAN server port
  bind: "0.0.0.0"    # Bind address

notifications:
  macos: true                   # Enable macOS notifications
  only_when_away: false         # Skip if a terminal is the frontmost app
  sound: "Ping"                 # macOS sound name (Ping, Basso, Funk, etc.)
  group_by_session: true        # Group notifications per session
  show_last_output: true        # Include last output in notification body
  output_lines: 3               # Lines of output to include
  redact_patterns:              # Auto-redact sensitive info from notifications
    - '(?i)(token|password|secret|key|api_key)=\S+'

detection:
  timeout_seconds: 30    # Timeout-based idle threshold
  cooldown_seconds: 5    # Minimum gap between notifications
```

### Custom patterns: `~/.jigai/patterns.yaml`

Add your own tools or override built-in patterns:

```yaml
custom_tools:
  my_agent:
    name: "My Custom Agent"
    idle_patterns:
      - 'READY>'
      - 'awaiting instruction'
      - '(?i)what would you like'

overrides:
  timeout_seconds: 45    # Override global timeout
```

---

## Commands

```bash
# Watch commands
jigai watch <cmd>                # Wrap a command, notify on idle
jigai watch --tool <key> <cmd>  # Override tool auto-detection
jigai watch --timeout 60 <cmd>  # Override idle timeout
jigai watch --no-notify <cmd>   # Disable macOS notifications
jigai watch --no-server <cmd>   # Don't push events to the server

# Server (for mobile / LAN notifications)
jigai server start               # Start server on default port 9384
jigai server start --port 8080   # Custom port
jigai server status              # Check if server is running

# Configuration
jigai config init                # Create default ~/.jigai/config.yaml
jigai config show                # Dump current configuration as JSON
jigai config test "<line>"       # Test if a line matches any pattern

# Info
jigai patterns                   # Show all loaded patterns and timeouts
jigai sessions                   # List active sessions (requires server)
jigai --version                  # Print version
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    jigai watch claude                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   stdin ──▶ PTY Proxy ──▶ Claude Code                  │
│             (pty_proxy)    (child proc)                  │
│                │                                         │
│   stdout ◀─── │ ──────────────────────────────────────  │
│                │                                         │
│                ▼                                         │
│        Idle Detector                                     │
│        (detector.py)                                     │
│         • ANSI strip                                     │
│         • Pattern match ──▶ match found ──┐              │
│         • Timeout check ──▶ N seconds ────┤              │
│                                           ▼              │
│                                    Notification          │
│                               ┌──────────────────┐      │
│                               │ macOS banner     │      │
│                               │ (terminal-notif) │      │
│                               │ Server push      │      │
│                               │ (WebSocket/HTTP) │      │
│                               └──────────────────┘      │
└─────────────────────────────────────────────────────────┘

┌──────────────────────────────────┐
│  jigai server start              │
│  FastAPI + WebSocket             │
│  mDNS/Bonjour broadcast          │──▶  Mobile App (v0.2)
│  REST API for session tracking   │     (React Native, LAN)
└──────────────────────────────────┘
```

---

## Development

```bash
git clone https://github.com/nafistiham/jigai.git
cd jigai
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy jigai/
```

### Project Structure

```
jigai/
├── jigai/
│   ├── cli.py            # Typer CLI entry point
│   ├── config.py         # Config management (Pydantic + YAML)
│   ├── models.py         # Session and IdleEvent data models
│   ├── notifier/
│   │   └── macos.py      # macOS notifications (osascript + terminal-notifier)
│   ├── server/
│   │   ├── app.py        # FastAPI REST + WebSocket server
│   │   ├── client.py     # HTTP client (watcher → server)
│   │   ├── discovery.py  # mDNS/Bonjour service broadcasting
│   │   └── ws_manager.py # WebSocket connection manager
│   └── watcher/
│       ├── detector.py   # Idle detection engine
│       ├── patterns.py   # Pattern registry and loader
│       ├── pty_proxy.py  # Transparent PTY proxy
│       └── watcher.py    # Session orchestrator
├── patterns/
│   └── defaults.yaml     # Built-in tool patterns
└── tests/
    ├── test_config.py
    ├── test_detector.py
    ├── test_models.py
    └── test_patterns.py
```

---

## Publishing to PyPI

> For maintainers.

1. Bump `version` in `pyproject.toml`
2. Create a GitHub Release with tag `vX.Y.Z`
3. The [CI workflow](.github/workflows/publish.yml) auto-publishes to PyPI via Trusted Publishing

For the first publish, set up Trusted Publishing on PyPI:
1. Go to pypi.org → your project → **Publishing**
2. Add a trusted publisher: owner `nafistiham`, repo `jigai`, workflow `publish.yml`, environment `release`

---

## Roadmap

- [x] v0.1 — CLI + PTY proxy + idle detection + macOS notifications + LAN server
- [ ] v0.2 — React Native mobile app (iOS + Android), daemon mode
- [ ] v0.3 — Homebrew formula, Linux support (libnotify)
- [ ] v0.4 — Native Swift notification backend (Sequoia fix), web dashboard
- [ ] Future — Slack/Discord webhooks, Windows toast notifications

---

## Contributing

Contributions are welcome. Please open an issue before submitting a PR for non-trivial changes so we can discuss the approach.

```bash
# Fork, clone, create a branch
git checkout -b feat/your-feature

# Make changes, add tests
pytest

# Lint
ruff check .

# Open a PR against develop
```

---

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Built with frustration at missed Claude Code prompts.<br>
  <a href="https://github.com/nafistiham/jigai">github.com/nafistiham/jigai</a>
</p>
