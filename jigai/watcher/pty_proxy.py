"""PTY proxy — transparent terminal wrapper for monitoring AI tool output."""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import time
import tty
from typing import Callable, Optional


def _set_nonblocking(fd: int) -> None:
    """Set a file descriptor to non-blocking mode."""
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def _get_terminal_size() -> tuple[int, int]:
    """Get current terminal size (rows, cols)."""
    try:
        size = os.get_terminal_size()
        return (size.lines, size.columns)
    except OSError:
        return (24, 80)


def _set_pty_size(fd: int, rows: int, cols: int) -> None:
    """Set the PTY window size."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


class PtyProxy:
    """
    Transparent PTY proxy that wraps a child process.

    All I/O passes through unchanged — the child process behaves identically
    to running directly in the terminal. Output is simultaneously fed to a
    callback for idle detection.
    """

    def __init__(
        self,
        command: list[str],
        on_output: Callable[[bytes], None],
        on_exit: Optional[Callable[[int], None]] = None,
    ):
        """
        Args:
            command: Command + args to spawn (e.g., ["claude"]).
            on_output: Called with raw bytes from child stdout.
            on_exit: Called with exit code when child terminates.
        """
        self.command = command
        self.on_output = on_output
        self.on_exit = on_exit
        self._master_fd: Optional[int] = None
        self._child_pid: Optional[int] = None
        self._running = False
        self._old_termios: Optional[list] = None

    @property
    def child_pid(self) -> Optional[int]:
        return self._child_pid

    def run(self) -> int:
        """
        Run the child process in a PTY proxy. Blocks until child exits.

        Returns the child's exit code.
        """
        # Save terminal state and switch to raw mode
        stdin_fd = sys.stdin.fileno()
        try:
            self._old_termios = termios.tcgetattr(stdin_fd)
        except termios.error:
            self._old_termios = None

        # Create PTY pair
        self._master_fd, slave_fd = pty.openpty()

        # Set PTY size to match current terminal
        rows, cols = _get_terminal_size()
        _set_pty_size(self._master_fd, rows, cols)

        # Fork the child process
        self._child_pid = os.fork()

        if self._child_pid == 0:
            # === CHILD PROCESS ===
            os.close(self._master_fd)
            os.setsid()

            # Set the slave as the controlling terminal
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

            # Redirect stdin/stdout/stderr to slave PTY
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)

            if slave_fd > 2:
                os.close(slave_fd)

            # Execute the command
            os.execvp(self.command[0], self.command)

        # === PARENT PROCESS ===
        os.close(slave_fd)
        self._running = True

        # Handle SIGWINCH (terminal resize)
        def _handle_resize(signum, frame):
            rows, cols = _get_terminal_size()
            if self._master_fd is not None:
                try:
                    _set_pty_size(self._master_fd, rows, cols)
                except OSError:
                    pass

        signal.signal(signal.SIGWINCH, _handle_resize)

        # Switch stdin to raw mode so keystrokes pass through immediately
        if self._old_termios is not None:
            try:
                tty.setraw(stdin_fd)
            except termios.error:
                pass

        exit_code = self._io_loop(stdin_fd)

        # Restore terminal
        self._restore_terminal(stdin_fd)

        if self.on_exit:
            self.on_exit(exit_code)

        return exit_code

    def _io_loop(self, stdin_fd: int) -> int:
        """Main I/O loop — proxy data between user and child."""
        master_fd = self._master_fd
        assert master_fd is not None

        _set_nonblocking(master_fd)
        _set_nonblocking(stdin_fd)

        exit_code = 0

        while self._running:
            try:
                rlist, _, _ = select.select([master_fd, stdin_fd], [], [], 1.0)
            except (select.error, ValueError, OSError):
                break

            if master_fd in rlist:
                # Data from child → write to user's terminal + feed to detector
                try:
                    data = os.read(master_fd, 16384)
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)
                    self.on_output(data)
                except OSError as e:
                    if e.errno == errno.EIO:
                        break  # Child closed PTY
                    if e.errno != errno.EAGAIN:
                        break

            if stdin_fd in rlist:
                # Data from user → write to child
                try:
                    data = os.read(stdin_fd, 16384)
                    if not data:
                        break
                    os.write(master_fd, data)
                except OSError as e:
                    if e.errno != errno.EAGAIN:
                        break

            # Check if child is still alive
            try:
                pid, status = os.waitpid(self._child_pid, os.WNOHANG)
                if pid != 0:
                    if os.WIFEXITED(status):
                        exit_code = os.WEXITSTATUS(status)
                    else:
                        exit_code = -1
                    self._running = False
            except ChildProcessError:
                self._running = False

        # Drain any remaining output
        try:
            while True:
                data = os.read(master_fd, 16384)
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)
                self.on_output(data)
        except OSError:
            pass

        # Wait for child if still running
        if self._running:
            try:
                _, status = os.waitpid(self._child_pid, 0)
                if os.WIFEXITED(status):
                    exit_code = os.WEXITSTATUS(status)
            except ChildProcessError:
                pass

        # Clean up
        try:
            os.close(master_fd)
        except OSError:
            pass
        self._master_fd = None

        return exit_code

    def _restore_terminal(self, stdin_fd: int) -> None:
        """Restore original terminal settings."""
        if self._old_termios is not None:
            try:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, self._old_termios)
            except termios.error:
                pass

    def stop(self) -> None:
        """Stop the proxy and kill the child process."""
        self._running = False
        if self._child_pid:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
