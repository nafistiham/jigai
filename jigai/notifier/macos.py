"""macOS notification support via osascript and terminal-notifier."""

from __future__ import annotations

import shutil
import subprocess

_TERMINAL_APPS = {
    "terminal", "iterm2", "warp", "hyper", "alacritty",
    "kitty", "ghostty", "tabby", "rio",
}


def _has_terminal_notifier() -> bool:
    """Check if terminal-notifier is installed."""
    return shutil.which("terminal-notifier") is not None


def is_terminal_focused() -> bool:
    """Return True if a terminal app is currently the frontmost window."""
    try:
        result = subprocess.run(
            [
                "osascript", "-e",
                'tell application "System Events" to get name of first '
                'application process whose frontmost is true',
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        frontmost = result.stdout.strip().lower()
        return any(term in frontmost for term in _TERMINAL_APPS)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False  # Can't tell — assume not focused, allow notification


def notify_macos(
    title: str,
    message: str,
    subtitle: str | None = None,
    sound: str = "Ping",
    group: str | None = None,
) -> None:
    """
    Send a macOS notification.

    Uses terminal-notifier if available (richer features, click actions),
    falls back to osascript (zero dependencies).
    """
    # Sanitize inputs for shell safety
    title = _sanitize(title)
    message = _sanitize(message)
    if subtitle:
        subtitle = _sanitize(subtitle)

    if _has_terminal_notifier():
        _notify_terminal_notifier(title, message, subtitle, sound, group)
    else:
        _notify_osascript(title, message, subtitle, sound)


def _notify_osascript(
    title: str,
    message: str,
    subtitle: str | None = None,
    sound: str = "Ping",
) -> None:
    """Send notification via osascript (built into macOS)."""
    parts = [f'display notification "{message}"']
    parts.append(f'with title "{title}"')
    if subtitle:
        parts.append(f'subtitle "{subtitle}"')
    parts.append(f'sound name "{sound}"')

    script = " ".join(parts)

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass  # Silently fail — we're a notification, not critical


def _notify_terminal_notifier(
    title: str,
    message: str,
    subtitle: str | None = None,
    sound: str = "Ping",
    group: str | None = None,
) -> None:
    """Send notification via terminal-notifier (richer features)."""
    cmd = [
        "terminal-notifier",
        "-title", title,
        "-message", message,
        "-sound", sound,
    ]

    if subtitle:
        cmd += ["-subtitle", subtitle]

    if group:
        cmd += ["-group", f"jigai-{group}"]

    try:
        subprocess.run(cmd, capture_output=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Fall back to osascript
        _notify_osascript(title, message, subtitle, sound)


def _sanitize(text: str) -> str:
    """Sanitize text for use in osascript/shell commands."""
    # Replace characters that could break AppleScript strings
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ⏎ ")
