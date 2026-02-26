# JigAi (জিগাই)

<p align="center">
  <strong>জিগাই</strong> — Bangla for <em>"asking"</em> — Know when your AI agent is waiting for you.
</p>

<p align="center">
  <a href="https://github.com/nafistiham/jigai/actions/workflows/ci.yml"><img src="https://github.com/nafistiham/jigai/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey" alt="macOS only">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
</p>

---

A **tool-agnostic** terminal notification system that watches AI coding agents — Claude Code, Codex, Gemini CLI, Aider, or any custom tool — and notifies you via **macOS notifications** and optionally your **phone over LAN** the moment they go idle and need your input.

**No hooks. No per-tool config. Just wrap your command and go.**

```bash
pip install jigai
jigai watch claude
```

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [The Problem](#the-problem)
- [How JigAi Is Different](#how-jigai-is-different)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Supported Tools](#supported-tools)
- [Notification Setup](#notification-setup)
- [Known Issues and Caveats](#known-issues-and-caveats)
- [Configuration](#configuration)
- [Commands](#commands)
- [Architecture](#architecture)
- [Development](#development)
- [Publishing to PyPI](#publishing-to-pypi)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Prerequisites

- **macOS** — notifications use macOS APIs. Linux and Windows support is planned.
- **Python 3.10 or later**
- **[terminal-notifier](https://github.com/julienXX/terminal-notifier)** (strongly recommended) — required for banner popup notifications. Without it, notifications land silently in Notification Center.

```bash
brew install terminal-notifier
```

---

## The Problem

You kick off Claude Code on a big refactor, switch to your browser to research something, and come back 20 minutes later to find it asked a clarifying question in the first 30 seconds. You just wasted 20 minutes.

Every AI coding tool has this problem. Existing solutions all have significant limitations:

- **Hook-based tools** (Claude Code Notifier, ntfy integrations) require per-tool configuration that breaks across versions and doesn't work with tools that don't have hooks.
- **Cloud notification services** (Pushover, ntfy.sh) require accounts, subscriptions, or sending your terminal output to a third-party server.
- **Terminal replacements** (cmux) require abandoning your existing terminal setup.

**JigAi** fixes this with a single transparent PTY proxy that watches any terminal output, detects idle patterns, and notifies you — locally, privately, instantly.

---

## How JigAi Is Different

| Feature | ntfy / Pushover | Claude Code Notifier | cmux | JigAi |
|---|:---:|:---:|:---:|:---:|
| Works with **any** AI tool | ❌ manual wiring | ❌ Claude Code only | ✅ via hooks | ✅ auto-detect |
| **No per-tool config** needed | ❌ | ❌ | ❌ hooks required | ✅ |
| **Auto-detects** idle state | ❌ | ❌ hook-triggered | ❌ | ✅ |
| macOS notifications | ✅ | ✅ | ✅ | ✅ |
| **LAN mobile push** (no cloud) | ❌ cloud | ❌ | ❌ | ✅ |
| Works in **any terminal** | ✅ | ✅ | ❌ is the terminal | ✅ |
| **Free and open source** | ✅ ntfy | ❌ | ❌ | ✅ |
| **Privacy-first** (LAN only) | ❌ cloud | ✅ | ✅ | ✅ |

---

## How It Works

JigAi wraps your AI tool in a **PTY (pseudo-terminal) proxy**. Your tool runs exactly as normal — same colors, same interactivity, same behavior. JigAi intercepts the output stream silently in the background:

```
You type:  jigai watch claude
                │
                ▼
     ┌──────────────────────┐
     │    JigAi Watcher     │  ← sits here transparently
     │    (PTY proxy)       │
     └──────────┬───────────┘
                │  all I/O passed through unchanged
                ▼
     ┌──────────────────────┐
     │     Claude Code      │  ← behaves as if launched directly
     └──────────────────────┘
```

Idle detection uses three layers in order:
1. **Pattern match** — recognizes the idle prompt for known tools instantly
2. **Timeout fallback** — no output for N seconds = idle (works with any tool)
3. **Cooldown** — suppresses repeated notifications during a single idle period

When idle is detected, JigAi fires:
1. A **macOS notification** with the last meaningful output line
2. A **WebSocket push** to the JigAi server (if running)
3. Your phone receives the notification via the LAN server *(mobile app coming in v0.2)*

---

## Quick Start

### 1. Install

```bash
pip install jigai
brew install terminal-notifier   # recommended — enables banner popups
```

See [Notification Setup](#notification-setup) for the one-time macOS configuration required.

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

# Override tool name (custom idle prompts)
jigai watch --tool my_agent -- python agent.py
```

### 3. (Optional) Start the server for LAN mobile push

```bash
# Terminal 1 — keep the server running in the background
jigai server start

# Terminal 2 — watch your tool as normal
jigai watch claude
```

That's it. When your AI tool goes idle, you get notified.

---

## Supported Tools

| Tool | Detection | Notes |
|------|-----------|-------|
| Claude Code | Pattern + timeout | Built-in |
| OpenAI Codex CLI | Pattern + timeout | Built-in |
| Gemini CLI | Pattern + timeout | Built-in |
| Aider | Pattern + timeout | Built-in |
| OpenCode | Pattern + timeout | Built-in |
| Any custom tool | User-defined regex | Via `~/.jigai/patterns.yaml` |

The **timeout fallback** (default: 30s of silence = idle) means JigAi works with any tool out of the box, even ones not listed above.

---

## Notification Setup

JigAi tries two delivery mechanisms in order:

### 1. `terminal-notifier` — Recommended

Enables proper banner popup notifications.

```bash
brew install terminal-notifier
```

**One-time macOS configuration:**

1. Open **System Settings → Notifications → terminal-notifier**
2. Toggle **Allow Notifications** ON
3. Check **Desktop** *(required for the popup to appear on screen)*
4. Set **Alert Style** → **Persistent** (stays until dismissed) or **Temporary** (auto-dismisses after a few seconds)
5. Toggle **Play sound for notification** ON

### 2. `osascript` — Fallback

No installation required. Notifications appear in **Notification Center** but may not show as popup banners on macOS Sequoia (15.x). See [Known Issues](#known-issues-and-caveats).

---

## Known Issues and Caveats

Read this before filing a bug — most common issues are documented here.

---

### Focus Mode silences banner popups

**Symptom:** Notification appears in Notification Center, but the banner popup never shows — even with all settings correct.

**Cause:** macOS Focus (Do Not Disturb, Work, Personal, etc.) blocks notification banners from apps not on the allow list.

**Fix:**
1. **System Settings → Focus** → select your active Focus profile
2. **Allowed Notifications → Apps** → add **terminal-notifier**

One-time setup per Focus profile. This is the most common reason banners don't show.

---

### `terminal-notifier` on macOS Sequoia (15.x)

**Symptom:** Notifications appear in Notification Center but never pop as banners, or no notifications appear at all.

**Cause:** `terminal-notifier` has a [known compatibility issue on macOS 15](https://github.com/julienXX/terminal-notifier/issues/312), particularly on M-series chips. It predates the UserNotifications framework changes in Sequoia.

**Workarounds (try in order):**

1. Make sure Focus mode isn't blocking it (see above) — this is the cause 90% of the time.

2. Reset the notification registration cache:
   ```bash
   /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
     -kill -r -domain local -domain system -domain user
   ```
   Then re-open System Settings → Notifications → terminal-notifier and re-enable.

3. If banners still don't appear, notifications will still land in **Notification Center** via the `osascript` fallback — you won't get the popup, but the sound will still play.

A native Swift notification backend is planned for v0.2 which will resolve this permanently.

---

### Notifications fire while you're at the terminal

**By default this is intentional** — the sound cue is useful even when you're looking at the screen.

To suppress notifications when any terminal window is focused:

```yaml
# ~/.jigai/config.yaml
notifications:
  only_when_away: true
```

JigAi checks the frontmost macOS application. If it is Terminal, iTerm2, Warp, Ghostty, Alacritty, Kitty, Hyper, Tabby, or Rio, the notification is skipped.

---

### Display mirroring or screen sharing

**Symptom:** Notifications don't appear while screen sharing or using a mirrored display.

**Fix:** System Settings → Notifications → enable **"Allow notifications when mirroring or sharing the display"**

---

### Idle fires too early or too often

**Cause:** A pattern may match on output that looks like an idle prompt but isn't.

**Fix:** Raise the cooldown (minimum gap between notifications) or the timeout:

```yaml
# ~/.jigai/config.yaml
detection:
  timeout_seconds: 45    # wait longer before timeout-based idle
  cooldown_seconds: 10   # minimum seconds between consecutive notifications
```

Debug which lines trigger detection:

```bash
jigai config test "the output line you want to test"
```

---

### Pattern detection reliability for Claude Code

Claude Code renders a rich TUI with box-drawing characters and animated spinners. JigAi strips all ANSI codes and decorative Unicode before matching. If detection feels unreliable, fall back to a longer timeout:

```bash
jigai watch --timeout 60 claude
```

---

### Mobile notifications (iOS / Android) — not yet available

The mobile app is planned for **v0.2**. `jigai server start` runs the WebSocket server that the React Native app will connect to — the server-side is already live.

**iOS note:** iOS aggressively suspends background WebSocket connections. The v0.2 mobile app will document foreground/background behavior in detail. For fully reliable background delivery on iOS, a push notification relay option will be offered as an opt-in.

---

## Configuration

Initialize the config file with defaults:

```bash
jigai config init
```

### `~/.jigai/config.yaml` — full reference

```yaml
server:
  port: 9384          # LAN server port
  bind: "0.0.0.0"    # Bind address (0.0.0.0 = all interfaces)

notifications:
  macos: true                   # Enable macOS notifications
  only_when_away: false         # Skip notification if a terminal is focused
  sound: "Ping"                 # macOS sound name: Ping, Basso, Funk, Glass, etc.
  group_by_session: true        # Group notifications per session in NC
  show_last_output: true        # Include last meaningful output line in body
  output_lines: 3               # Lines of terminal context to capture
  redact_patterns:              # Patterns auto-redacted from notification body
    - '(?i)(token|password|secret|key|api_key)=\S+'

detection:
  timeout_seconds: 30    # Silence threshold for timeout-based idle
  cooldown_seconds: 5    # Minimum gap between consecutive notifications
```

### `~/.jigai/patterns.yaml` — custom tool patterns

```yaml
custom_tools:
  my_agent:
    name: "My Custom Agent"
    idle_patterns:
      - 'READY>'
      - 'awaiting instruction'
      - '(?i)what would you like'

overrides:
  timeout_seconds: 45
```

---

## Commands

```bash
# Watching
jigai watch <cmd>                # Wrap a command, notify on idle
jigai watch --tool <key> <cmd>  # Override tool auto-detection
jigai watch --timeout 60 <cmd>  # Override idle timeout
jigai watch --no-notify <cmd>   # Disable macOS notifications for this session
jigai watch --no-server <cmd>   # Don't push events to the server

# Server (LAN / mobile notifications)
jigai server start               # Start on default port 9384
jigai server start --port 8080   # Custom port
jigai server status              # Check if server is running

# Config
jigai config init                # Create ~/.jigai/config.yaml with defaults
jigai config show                # Print current configuration as JSON
jigai config test "<line>"       # Test if a line matches any idle pattern

# Info
jigai patterns                   # Show all loaded patterns and timeout settings
jigai sessions                   # List active sessions (requires server running)
jigai --version                  # Print version
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   jigai watch claude                     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│   stdin  ──▶  PTY Proxy  ──▶  Claude Code               │
│               (pty_proxy)      (child process)           │
│                   │                                      │
│   stdout  ◀───────┤ (passed through unchanged)           │
│                   │                                      │
│                   ▼                                      │
│           Idle Detector                                  │
│           (detector.py)                                  │
│            • strip ANSI / box-drawing chars              │
│            • pattern match ──▶ match found ──┐           │
│            • timeout check ──▶ N seconds ────┤           │
│                                              ▼           │
│                                     ┌────────────────┐   │
│                                     │ macOS banner   │   │
│                                     │ (terminal-nf.) │   │
│                                     │ Server push    │   │
│                                     │ (HTTP → WS)   │   │
│                                     └────────────────┘   │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────┐
│  jigai server start              │
│  FastAPI + WebSocket             │
│  mDNS/Bonjour broadcast          │──▶  Mobile App (v0.2)
│  REST API for session tracking   │     React Native, LAN-only
└──────────────────────────────────┘
```

---

## Development

```bash
git clone https://github.com/nafistiham/jigai.git
cd jigai
pip install -e ".[dev]"

pytest                  # run tests
ruff check .            # lint
mypy jigai/             # type check
```

### Project Structure

```
jigai/                       ← repo root
├── jigai/                   ← Python package
│   ├── cli.py               # Typer CLI entry point
│   ├── config.py            # Config management (Pydantic + YAML)
│   ├── models.py            # Session and IdleEvent data models
│   ├── notifier/
│   │   └── macos.py         # macOS notifications (osascript + terminal-notifier)
│   ├── server/
│   │   ├── app.py           # FastAPI REST + WebSocket server
│   │   ├── client.py        # HTTP client (watcher → server push)
│   │   ├── discovery.py     # mDNS/Bonjour service broadcasting
│   │   └── ws_manager.py    # WebSocket connection manager
│   └── watcher/
│       ├── detector.py      # Idle detection engine
│       ├── patterns.py      # Pattern registry and loader
│       ├── pty_proxy.py     # Transparent PTY proxy
│       └── watcher.py       # Session orchestrator
├── patterns/
│   └── defaults.yaml        # Built-in tool patterns
└── tests/
```

---

## Publishing to PyPI

> For maintainers.

### First release

PyPI's **Trusted Publishing** requires the project to be registered before it can be used. The cleanest first-publish flow:

**Option A — Pending Publisher (no manual upload needed):**
1. Register at [pypi.org](https://pypi.org/account/register)
2. Go to [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing)
3. Under **"Add a new pending publisher"**, fill in:
   - PyPI project name: `jigai`
   - Owner: `nafistiham`, Repository: `jigai`
   - Workflow filename: `publish.yml`
   - Environment: `release`
4. Create a GitHub Release with tag `v0.1.0` — the workflow will create the PyPI project and publish in one step.

**Option B — Manual first upload, then Trusted Publishing for subsequent releases:**
```bash
pip install build twine
python -m build
twine upload dist/*          # prompts for PyPI credentials
```
Then set up Trusted Publishing on your existing project for future releases.

### Subsequent releases

1. Bump `version` in `pyproject.toml`
2. Create a GitHub Release with tag `vX.Y.Z`
3. The [publish workflow](.github/workflows/publish.yml) runs automatically via Trusted Publishing — no tokens to manage.

---

## Roadmap

- [x] **v0.1** — CLI · PTY proxy · idle detection · macOS notifications · LAN WebSocket server
- [ ] **v0.2** — React Native mobile app (iOS + Android) · daemon mode
- [ ] **v0.3** — Homebrew formula · Linux support (libnotify)
- [ ] **v0.4** — Native Swift notification backend (fixes Sequoia) · web dashboard
- [ ] **Future** — Slack/Discord webhooks · Windows toast notifications

---

## Contributing

Contributions are welcome. For non-trivial changes, please open an issue first so we can align on the approach before you invest time writing code.

### Branch strategy

```
main       ← stable, matches latest release
develop    ← integration branch, target for PRs
feat/*     ← feature branches, branched from develop
fix/*      ← bug fix branches, branched from develop
```

Always open PRs against **`develop`**, not `main`.

### Workflow

```bash
# Fork the repo, then:
git clone https://github.com/<your-username>/jigai.git
cd jigai
git checkout develop
git checkout -b feat/your-feature

pip install -e ".[dev]"

# Make changes, write tests
pytest
ruff check .

# Commit using conventional commits
git commit -m "feat(watcher): add support for foo tool"
git commit -m "fix(notifier): handle edge case on Sonoma"
git commit -m "docs: update custom patterns example"

git push -u origin feat/your-feature
# Open a PR → base: develop
```

### Commit convention

```
feat(scope):  new feature
fix(scope):   bug fix
docs:         documentation only
test:         tests only
ci:           CI/CD changes
chore:        build, config, tooling
```

---

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Built with frustration at missed Claude Code prompts.<br>
  <a href="https://github.com/nafistiham/jigai">github.com/nafistiham/jigai</a>
</p>
