"""
Fast PipeWire video capture for Wayland using pipewire-capture library.
Uses xdg-desktop-portal for window selection - works on KDE, GNOME, etc.
"""
import threading
import time
import numpy as np
from typing import List, Callable, Optional

try:
    from pipewire_capture import PortalCapture, CaptureStream, is_available
    PIPEWIRE_AVAILABLE = True
except ImportError:
    PIPEWIRE_AVAILABLE = False


class PipeWireFastCapture:
    """
    Fast screen capture using PipeWire via xdg-desktop-portal.
    This is the recommended capture method for Wayland.

    Note: The 'region' parameter is ignored - PipeWire uses the system picker.
    """

    MAX_RAM_BYTES = 4 * 1024 * 1024 * 1024  # 4GB

    def __init__(self, region=None, fps: int = 12, on_memory_full: Callable = None, on_selection_cancelled: Callable = None):
        self.region = region  # Ignored - PipeWire uses system picker
        self.fps = fps
        self.interval = 1.0 / fps
        self.frames: List[np.ndarray] = []
        self.capturing = False
        self.thread: Optional[threading.Thread] = None
        self.on_memory_full = on_memory_full
        self.on_selection_cancelled = on_selection_cancelled
        self.current_memory = 0
        self.portal = None
        self.stream = None
        self.capture_interval = 1.0 / fps
        self._started = False
        self._lock = threading.Lock()
        self._selection_thread = None

    def start(self):
        """Start capturing in background thread. Shows window picker."""
        if not PIPEWIRE_AVAILABLE:
            print("PipeWire capture not available!")
            return False

        self.frames = []
        self.current_memory = 0
        self._started = False
        self.capturing = False
        self.session = None

        # Run selection in background thread so it doesn't block Qt
        def do_selection_and_capture():
            try:
                print("[PipeWire] Creating portal...")
                self.portal = PortalCapture()

                print("[PipeWire] Showing selection dialog...")
                # This is BLOCKING - shows dialog and returns PortalSession or None
                session = self.portal.select_window()
                print(f"[PipeWire] Selection result: {session}")

                if session is None:
                    print("[PipeWire] Selection cancelled")
                    # Notify main app so it can reset state
                    if self.on_selection_cancelled:
                        self.on_selection_cancelled()
                    return

                print(f"[PipeWire] Session: fd={session.fd}, node_id={session.node_id}")
                print(f"[PipeWire] Size: {session.width}x{session.height}")
                self.session = session

                # Start capturing
                self.capturing = True
                self._started = True  # Mark that capture has actually started
                self.stream = CaptureStream(session.fd, session.node_id,
                                           session.width, session.height,
                                           capture_interval=self.capture_interval)
                self.stream.start()

                print(f"[PipeWire] Capture started at ~{1.0/self.capture_interval:.0f} fps")

                # Run capture loop in this thread
                self._capture_loop()

            except Exception as e:
                print(f"[PipeWire] Error: {e}")
                import traceback
                traceback.print_exc()
                self.capturing = False

        # Start selection/capture in background
        self._selection_thread = threading.Thread(target=do_selection_and_capture, daemon=True)
        self._selection_thread.start()

        print("[PipeWire] Selection thread started, returning True")
        print(f"[PipeWire] Initial state: capturing={self.capturing}, frames={len(self.frames)}")
        return True

    def _capture_loop(self):
        """Main capture loop."""
        next_frame_time = time.time()
        frames_this_second = 0
        last_second = time.time()
        iteration = 0

        print("[PipeWire] Capture loop starting...")
        print(f"[PipeWire] capturing={self.capturing}, stream={self.stream}")

        while self.capturing and self.stream:
            current_time = time.time()
            iteration += 1

            if current_time >= next_frame_time:
                try:
                    if iteration % 30 == 0:  # Log every 30 iterations
                        print(f"[PipeWire] Getting frame... (iteration {iteration}, capturing={self.capturing})")

                    frame = self.stream.get_frame()

                    if iteration % 30 == 0:
                        print(f"[PipeWire] Got frame: {frame is not None, type(frame) if frame is not None else 'None'}")

                    if frame is not None:
                        print(f"[PipeWire] Frame shape: {frame.shape if hasattr(frame, 'shape') else 'no shape'}")

                        # Convert BGRA to BGR
                        if len(frame.shape) == 3 and frame.shape[2] == 4:
                            frame = frame[:, :, :3].copy()

                        with self._lock:
                            self.frames.append(frame)

                        frames_this_second += 1
                        self.current_memory += frame.nbytes
                        print(f"[PipeWire] Frame stored! Total: {len(self.frames)}, Memory: {self.current_memory / (1024*1024):.1f}MB")

                        # Check memory limit
                        if self.current_memory >= self.MAX_RAM_BYTES:
                            print(f"[PipeWire] Memory limit reached, stopping...")
                            self.capturing = False
                            if self.on_memory_full:
                                self.on_memory_full()
                            break
                    else:
                        if iteration % 30 == 0:
                            print(f"[PipeWire] get_frame() returned None")

                    next_frame_time += self.capture_interval

                    # Log FPS
                    if current_time - last_second >= 1.0:
                        print(f"[PipeWire] {frames_this_second} fps, total: {len(self.frames)} frames")
                        frames_this_second = 0
                        last_second = current_time

                    # Skip if behind
                    if current_time > next_frame_time + self.capture_interval * 3:
                        while current_time > next_frame_time:
                            next_frame_time += self.capture_interval

                except Exception as e:
                    print(f"[PipeWire] Frame error: {e}")

            else:
                sleep_time = min(0.01, next_frame_time - current_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def stop(self) -> List[np.ndarray]:
        """Stop capturing and return frames."""
        print(f"[PipeWire] stop() called. Current state: capturing={self.capturing}, frames={len(self.frames)}")

        self.capturing = False

        if self.stream:
            try:
                self.stream.stop()
                print("[PipeWire] Stream stopped")
            except Exception as e:
                print(f"[PipeWire] Error stopping stream: {e}")

        if self._selection_thread:
            print(f"[PipeWire] Waiting for selection thread...")
            self._selection_thread.join(timeout=5)
            print(f"[PipeWire] Selection thread finished")

        if self.thread:
            self.thread.join(timeout=3)

        if self.session:
            try:
                self.session.close()
                print("[PipeWire] Session closed")
            except Exception as e:
                print(f"[PipeWire] Error closing session: {e}")

        with self._lock:
            frames = self.frames.copy()

        print(f"[PipeWire] Capture stopped. Total frames: {len(frames)}")
        if len(frames) == 0:
            print("[PipeWire] WARNING: No frames captured!")
            print(f"[PipeWire] Debug: stream={self.stream}, session={self.session}")
        return frames

    def get_frame_count(self) -> int:
        with self._lock:
            return len(self.frames)

    def has_started(self) -> bool:
        """Check if capture has actually started (selection complete)."""
        return self._started

    @staticmethod
    def is_available() -> bool:
        return PIPEWIRE_AVAILABLE and is_available()


# Check availability
if PIPEWIRE_AVAILABLE:
    if is_available():
        print("PipeWire fast capture available (Wayland)")
    else:
        print("PipeWire capture library available but not on Wayland")
else:
    print("PipeWire capture not available - install pipewire-capture")
