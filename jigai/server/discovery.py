"""mDNS/Bonjour service discovery for JigAi server."""

from __future__ import annotations

import socket

from rich.console import Console

from jigai import __version__

console = Console(stderr=True)


def get_local_ip() -> str:
    """Get the local IP address of this machine on the LAN."""
    try:
        # Connect to a public address to determine local interface
        # (no data is actually sent)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ServiceBroadcaster:
    """Broadcasts JigAi server via mDNS/Bonjour for auto-discovery."""

    def __init__(self, port: int = 9384):
        self.port = port
        self._zeroconf = None
        self._info = None

    def start(self) -> bool:
        """Start broadcasting the service. Returns True on success."""
        try:
            from zeroconf import ServiceInfo, Zeroconf

            local_ip = get_local_ip()
            hostname = socket.gethostname()

            self._info = ServiceInfo(
                "_jigai._tcp.local.",
                f"JigAi on {hostname}._jigai._tcp.local.",
                addresses=[socket.inet_aton(local_ip)],
                port=self.port,
                properties={
                    "version": __version__,
                    "hostname": hostname,
                },
                server=f"{hostname}.local.",
            )

            self._zeroconf = Zeroconf()
            self._zeroconf.register_service(self._info)

            console.print(
                f"  [dim]mDNS: Broadcasting as [cyan]_jigai._tcp.local.[/cyan] "
                f"at {local_ip}:{self.port}[/dim]"
            )
            return True

        except ImportError:
            console.print(
                "  [dim yellow]mDNS: zeroconf not installed, "
                "mobile auto-discovery disabled[/dim yellow]"
            )
            return False
        except Exception as e:
            console.print(f"  [dim yellow]mDNS: Failed to start ({e})[/dim yellow]")
            return False

    def stop(self) -> None:
        """Stop broadcasting."""
        if self._zeroconf and self._info:
            try:
                self._zeroconf.unregister_service(self._info)
                self._zeroconf.close()
            except Exception:
                pass
            self._zeroconf = None
            self._info = None
