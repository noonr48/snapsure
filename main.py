#!/usr/bin/env python3
"""
WayYaSnitch - Screen Stitcher for KDE Plasma Wayland
CPU-only screen capture and stitching tool.

Usage: python main.py
Capture: Click tray icon (green "S")
"""
import sys
import os
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check for single instance
LOCK_FILE = "/tmp/wayyasnitch.lock"
def check_single_instance():
    """Ensure only one instance is running."""
    import fcntl
    try:
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        print("Another instance is already running!")
        sys.exit(1)

lock_fd = check_single_instance()

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, QRect, QTimer
from PyQt5.QtGui import QGuiApplication, QIcon, QPixmap, QPainter, QColor, QFont

from capture.selection import SelectionOverlay
from capture.qt_capture import TimerCapture, HAS_PIPEWIRE_CAPTURE
from stitch.matcher import stitch_frames
from output.pdf_generator import save_as_pdf, save_as_image
from utils.notifications import notify


class WayYaSnitch:
    """Main application - uses grim for Wayland screen capture."""

    STATE_IDLE = 0
    STATE_SELECTING = 1
    STATE_CAPTURING = 2
    STATE_PROCESSING = 3

    def __init__(self, app):
        self.app = app
        self.state = self.STATE_IDLE
        self.capture_region = QRect()
        self.capturer = None
        self.selection_overlay = None
        self.tray_icon = None
        self.tray_menu = None
        self.green_icon = None
        self.red_icon = None

    def toggle_capture(self):
        """Toggle between idle/capturing states."""
        if self.state == self.STATE_IDLE:
            if HAS_PIPEWIRE_CAPTURE:
                # PipeWire has its own picker - skip region selection
                self.capture_region = QRect()  # Empty region
                self.start_capturing()
            else:
                # Spectacle needs manual region selection
                self.start_selection()
        elif self.state == self.STATE_CAPTURING:
            self.stop_capture()

    def start_selection(self):
        """Show selection overlay for region selection (Spectacle only)."""
        self.state = self.STATE_SELECTING
        notify("WayYaSnitch", "Drag to select capture region")

        self.selection_overlay = SelectionOverlay()
        self.selection_overlay.selection_complete.connect(self.on_selection_complete)
        self.selection_overlay.show()

    def on_selection_complete(self, region: QRect):
        """Handle completed region selection."""
        self.capture_region = region
        self.start_capturing()

    def start_capturing(self):
        """Start capturing frames."""
        self.state = self.STATE_CAPTURING
        self._set_tray_recording(True)

        if HAS_PIPEWIRE_CAPTURE:
            notify("WayYaSnitch", "Select window/screen in dialog, then scroll!")
        else:
            notify("WayYaSnitch", "Recording... Scroll slowly!")

        # Create capturer with memory full callback
        # Higher FPS (12) for better overlap detection with smaller overlaps
        self.capturer = TimerCapture(
            self.capture_region,
            fps=12,  # 12 fps = ~83ms between frames, smaller overlaps
            on_memory_full=self.stop_capture,  # Auto-stitch when memory full
            on_selection_cancelled=self.on_selection_cancelled  # Handle cancelled selection
        )
        self.capturer.start()

    def on_selection_cancelled(self):
        """Handle when user cancels the window selection dialog."""
        print("[DEBUG] Window selection was cancelled - resetting to idle")
        self.state = self.STATE_IDLE
        self._set_tray_recording(False)
        self.capturer = None
        notify("WayYaSnitch", "Selection cancelled")

    def stop_capture(self):
        """Stop capturing and process frames."""
        if self.capturer is None:
            return

        # Check if capture has actually started (for PipeWire)
        if hasattr(self.capturer, 'has_started') and not self.capturer.has_started():
            notify("WayYaSnitch", "Still waiting for window selection...", "warning")
            print("[DEBUG] Cannot stop - window selection not complete yet")
            return

        self.state = self.STATE_PROCESSING
        self._set_tray_recording(False)

        frames = self.capturer.stop()
        frame_count = len(frames)

        print(f"=== CAPTURE DEBUG ===")
        print(f"Total frames captured: {frame_count}")
        if frame_count > 0:
            print(f"Frame 0 size: {frames[0].shape}")
            if frame_count > 1:
                print(f"Frame 1 size: {frames[1].shape}")

        if frame_count < 2:
            notify("WayYaSnitch", f"Only {frame_count} frames. Scroll more!", "critical")
            self.state = self.STATE_IDLE
            return

        notify("WayYaSnitch", f"Stitching {frame_count} frames...")

        # Stitch frames together
        result = stitch_frames(frames)
        print(f"Stitched result size: {result.shape if result is not None else 'None'}")

        if result is None:
            notify("WayYaSnitch", "Stitching failed!", "critical")
            self.state = self.STATE_IDLE
            return

        try:
            pdf_path = save_as_pdf(result)
            png_path = pdf_path.replace('.pdf', '.png')
            save_as_image(result, png_path)
            notify("WayYaSnitch", f"Saved {frame_count} frames → {result.shape[0]}px tall")
        except Exception as e:
            notify("WayYaSnitch", f"Save failed: {e}", "critical")

        self.state = self.STATE_IDLE
        self.capturer = None

    def _set_tray_recording(self, recording: bool):
        """Change tray icon color based on recording state."""
        if self.tray_icon:
            if recording:
                self.tray_icon.setIcon(self.red_icon)
                self.tray_icon.setToolTip("WayYaSnitch - RECORDING (click to stop)")
            else:
                self.tray_icon.setIcon(self.green_icon)
                self.tray_icon.setToolTip("WayYaSnitch - Click to capture")

    def update_tray_tooltip(self):
        """Update tray tooltip with current state."""
        if self.tray_icon:
            states = {
                self.STATE_IDLE: "Idle - Click to capture",
                self.STATE_SELECTING: "Selecting region...",
                self.STATE_CAPTURING: "Capturing - Click to stop",
                self.STATE_PROCESSING: "Processing..."
            }
            self.tray_icon.setToolTip(f"WayYaSnitch - {states[self.state]}")


def setup_tray_icon(app, snitch):
    """Create system tray icon."""
    tray = QSystemTrayIcon(app)

    # Create green icon (idle)
    green_pixmap = QPixmap(64, 64)
    green_pixmap.fill(Qt.transparent)
    painter = QPainter(green_pixmap)
    painter.setPen(QColor(0, 255, 0))
    painter.setFont(QFont("Arial", 40, QFont.Bold))
    painter.drawText(green_pixmap.rect(), Qt.AlignCenter, "S")
    painter.end()
    snitch.green_icon = QIcon(green_pixmap)

    # Create red icon (recording)
    red_pixmap = QPixmap(64, 64)
    red_pixmap.fill(Qt.transparent)
    painter = QPainter(red_pixmap)
    painter.setPen(QColor(255, 0, 0))
    painter.setFont(QFont("Arial", 40, QFont.Bold))
    painter.drawText(red_pixmap.rect(), Qt.AlignCenter, "S")
    painter.end()
    snitch.red_icon = QIcon(red_pixmap)

    tray.setIcon(snitch.green_icon)

    # Create menu
    menu = QMenu()

    capture_action = QAction("Start Capture", menu)
    capture_action.triggered.connect(snitch.toggle_capture)
    menu.addAction(capture_action)

    menu.addSeparator()

    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.setToolTip("WayYaSnitch - Click to capture")

    # Click to toggle
    def on_activated(reason):
        if reason == QSystemTrayIcon.Trigger:
            snitch.toggle_capture()
        snitch.update_tray_tooltip()

    tray.activated.connect(on_activated)
    tray.show()

    tray.showMessage("WayYaSnitch", "Click tray icon to start capture")

    return tray


def main():
    """Main entry point."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("WayYaSnitch")
    app.setQuitOnLastWindowClosed(False)

    snitch = WayYaSnitch(app)
    snitch.tray_icon = setup_tray_icon(app, snitch)

    # Handle signals
    signal.signal(signal.SIGINT, lambda s, f: app.quit())
    signal.signal(signal.SIGTERM, lambda s, f: app.quit())

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
