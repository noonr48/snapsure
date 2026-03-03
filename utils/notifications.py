"""Desktop notifications for WayYaSnitch."""
import subprocess
import sys


def notify(title: str, message: str, urgency: str = "normal") -> None:
    """Send desktop notification using notify-send."""
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, title, message],
            check=False
        )
    except FileNotFoundError:
        # Fallback to console if notify-send not available
        print(f"[{title}] {message}", file=sys.stderr)
