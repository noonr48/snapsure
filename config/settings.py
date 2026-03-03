"""Configuration settings for WayYaSnitch."""
import os
from datetime import datetime


class Settings:
    """Application settings - CPU only, no GPU acceleration."""

    # Capture settings
    FPS = 20
    CAPTURE_INTERVAL_MS = 1000 // FPS  # 50ms

    # Stitching settings
    MIN_OVERLAP = 50
    MAX_OVERLAP = 500
    MATCH_THRESHOLD = 0.8  # Template match confidence

    # Output settings
    OUTPUT_DIR = os.path.expanduser("~/Desktop")
    OUTPUT_PREFIX = "scroll_capture"

    # Selection overlay
    OVERLAY_OPACITY = 100  # 0-255
    BORDER_COLOR = (0, 255, 0)  # Green
    BORDER_WIDTH = 3

    # Hotkey
    HOTKEY = "Ctrl+`"

    @classmethod
    def get_output_path(cls, ext: str = "pdf") -> str:
        """Generate timestamped output path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(cls.OUTPUT_DIR, f"{cls.OUTPUT_PREFIX}_{timestamp}.{ext}")
