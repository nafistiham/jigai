# JigAi — Handoff Context

> One-stop doc for picking up work on a new machine.

---

## Repos

| Repo | GitHub | Local path |
|------|--------|------------|
| Python server + CLI | [nafistiham/jigai](https://github.com/nafistiham/jigai) | `JigAi/` |
| React Native app | [nafistiham/jigai-app](https://github.com/nafistiham/jigai-app) | `jigai-app/` |

Both repos sit as siblings:
```
~/Desktop/Learn/Projects/Personal/
├── JigAi/          ← Python server (this repo)
└── jigai-app/      ← React Native app
```

---

## New Machine Setup

### 1. Clone both repos
```bash
cd ~/Desktop/Learn/Projects/Personal
git clone https://github.com/nafistiham/jigai.git JigAi
git clone https://github.com/nafistiham/jigai-app.git jigai-app
```

### 2. JigAi server
```bash
cd JigAi/jigai
pip install -e ".[dev]"

# Verify
pytest                    # should pass all 72 tests
jigai --version
```

### 3. jigai-app
```bash
cd jigai-app
npm install
npx expo prebuild         # regenerates ios/ and android/ with native deps

# Run on iOS simulator
npx expo run:ios

# Tests
npm test
```

> **Note:** `ios/.xcode.env.local` is gitignored (machine-specific node path).
> Expo prebuild recreates it automatically — nothing to copy manually.

---

## Environment / Secrets

**No secrets anywhere.** Neither repo uses API keys, tokens, or cloud services.

| File | Status | Action needed |
|------|--------|---------------|
| `ios/.xcode.env.local` | gitignored, auto-generated | None — `expo prebuild` recreates it |
| `~/.jigai/config.yaml` | user config, not in git | Optional: run `jigai config init` |

---

## Current Status

### JigAi server (v0.1.0) — ready to publish

Everything for v0.1 is **complete and merged to `main`**.

**What works:**
- PTY proxy: `jigai watch claude` wraps any AI tool transparently
- Idle detection: pattern match + timeout + cooldown
- Built-in patterns: Claude Code, Codex, Gemini CLI, Aider, OpenCode
- User-configurable patterns via `~/.jigai/patterns.yaml`
- macOS notifications (terminal-notifier + osascript fallback)
- `notification_body` field: pre-cleaned single line, strips box-drawing/separator chars
- FastAPI server: REST + WebSocket for mobile push
- mDNS/Bonjour broadcast for phone auto-discovery
- 72 passing tests

**What's NOT done (v0.2+):**
- [ ] Daemon mode (`jigai daemon start/stop`) — currently server must stay in foreground
- [ ] PyPI publish — package is ready, just needs the first PyPI release (see README § Publishing)
- [ ] Homebrew formula
- [ ] Linux support (libnotify)
- [ ] Native Swift notification backend (fixes macOS Sequoia banner bug)

### jigai-app — core working, needs polish

**What works:**
- WebSocket connection to `jigai server`
- Auto-discovery via mDNS (react-native-zeroconf)
- Events tab: live event list with EventCard (tool name, notification_body, working dir, badge)
- In-app banner on new idle event
- Push notifications via expo-notifications
- Settings tab: manual server IP override
- 28 passing tests

**What's NOT done:**
- [ ] Android testing — never run on Android emulator/device
- [ ] Background notification reliability on iOS (iOS suspends WebSocket in background)
  - May need push notification relay or background fetch polling
- [ ] Empty/error states polish (connection lost banner, retry UX)
- [ ] App icon and splash screen (currently Expo defaults)
- [ ] TestFlight / App Store submission
- [ ] README polish (screenshots, demo GIF)

---

## Key Architecture Notes

### Server → App data flow
```
jigai watch claude
    → idle detected
    → HTTP POST /events  (watcher.py → server/client.py)
    → FastAPI stores event
    → WebSocket broadcast to all connected clients
    → app receives IdleEvent JSON
    → scheduleIdleNotification() fires push notification
    → EventCard renders in events list
```

### IdleEvent shape (shared between server and app)
```typescript
{
  session_id: string       // UUID per jigai watch session
  tool_name: string        // "Claude Code", "Aider", etc.
  working_dir: string      // shortened path, e.g. "~/projects/foo"
  last_output: string      // raw terminal buffer (never display directly)
  notification_body: string // pre-cleaned single line — USE THIS for display
  idle_seconds: number
  detection_method: string // "pattern" | "timeout"
  timestamp: string        // ISO8601
  server_time: string      // ISO8601
}
```

> **Critical:** Always use `notification_body` for display, never `last_output`.
> `last_output` may contain box-drawing chars and separator lines.
> `notification_body` is empty string `""` when no meaningful line was found — show nothing.

### Server port
Default: **9384**. WebSocket at `ws://[ip]:9384/ws`.

### Server startup
```bash
jigai server start    # runs uvicorn on port 9384, blocks terminal
```
No daemon mode yet — keep in a separate terminal tab.

---

## Git Workflow

Both repos use the same convention:

```
main ← develop ← feat/* / fix/*
```

- Rebase merge only — no squash, no merge commits
- PRs always target `develop`
- Never add `Co-Authored-By` trailers to commits

```bash
git checkout develop
git checkout -b fix/my-fix
# ... work ...
git push -u origin fix/my-fix
gh pr create   # target: develop
```

---

## Running Everything Together

```bash
# Terminal 1 — server
cd JigAi/jigai
jigai server start

# Terminal 2 — watch Claude
jigai watch claude

# Terminal 3 — app on simulator
cd jigai-app
npx expo run:ios
```

Phone on same LAN will auto-discover the server via mDNS. No IP config needed.

---

## Next Priorities (suggested order)

1. **Publish to PyPI** — register pending publisher on pypi.org, create GitHub Release v0.1.0
2. **Daemon mode** — `jigai daemon start/stop` so server runs in background without a dedicated terminal
3. **Android testing** — run `npx expo run:android` on an emulator, fix any platform issues
4. **iOS background notifications** — investigate WebSocket suspend; consider background fetch polling as fallback
5. **App polish** — icon, splash, empty states, screenshots for README
