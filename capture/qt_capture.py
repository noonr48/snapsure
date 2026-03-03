"""Fast screen capture using xdg-desktop-portal + PipeWire for KDE Wayland."""
import subprocess
import threading
import time
import os
import sys
from PyQt5.QtCore import QRect
from PIL import Image
import numpy as np

# Try to import pipewire-capture for fast capture
HAS_PIPEWIRE_CAPTURE = False
try:
    from pipewire_capture import PortalCapture, CaptureStream, is_available
    HAS_PIPEWIRE_CAPTURE = is_available()
    if HAS_PIPEWIRE_CAPTURE:
        print("pipewire-capture available for fast PipeWire capture")
except ImportError:
    print("pipewire-capture not available, using slower Spectacle fallback")

# Try to import GStreamer for fast PipeWire capture
HAS_GSTREAMER = False
try:
    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GstApp', '1.0')
    from gi.repository import Gst, GLib
    Gst.init(None)
    HAS_GSTREAMER = True
except Exception as e:
    print(f"GStreamer not available: {e}")


class PipeWireCapture:
    """Fast screen capture using PipeWire via xdg-desktop-portal."""

    def __init__(self, region: QRect, fps: int = 20):
        self.region = region
        self.fps = fps
        self.frames = []
        self.capturing = False
        self.pipeline = None
        self.mainloop = None
        self.thread = None

    def _on_new_sample(self, sink):
        """Callback for new video samples from GStreamer."""
        try:
            sample = sink.emit('pull-sample')
            if sample is None:
                return 0  # GST_FLOW_OK

            buffer = sample.get_buffer()
            caps = sample.get_caps()

            # Get video dimensions from caps
            structure = caps.get_structure(0)
            width = structure.get_value('width')
            height = structure.get_value('height')

            # Map buffer for reading
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                return 0

            try:
                # Convert to numpy array
                data = map_info.data
                frame = np.frombuffer(data, dtype=np.uint8)

                # Assuming BGRA format from pipewiresrc
                frame = frame.reshape((height, width, 4))

                # Crop to region if needed
                x = min(self.region.x(), width - 1)
                y = min(self.region.y(), height - 1)
                w = min(self.region.width(), width - x)
                h = min(self.region.height(), height - y)

                if x > 0 or y > 0 or w < width or h < height:
                    frame = frame[y:y+h, x:x+w]

                # Convert BGRA to BGR
                frame = frame[:, :, :3].copy()

                self.frames.append(frame)

            finally:
                buffer.unmap(map_info)

            return 0  # GST_FLOW_OK

        except Exception as e:
            print(f"Sample error: {e}")
            return 0

    def _run_pipeline(self):
        """Run the GStreamer pipeline in a separate thread."""
        # Create pipeline for PipeWire screen capture
        # This will show a portal dialog for screen selection
        pipeline_str = f"""
            pipewiresrc do-timestamp=true !
            video/x-raw,framerate={self.fps}/1 !
            videoconvert !
            video/x-raw,format=BGRA !
            appsink name=sink emit-signals=true max-buffers=1 drop=true
        """

        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            sink = self.pipeline.get_by_name('sink')
            sink.connect('new-sample', self._on_new_sample)

            # Start pipeline
            self.pipeline.set_state(Gst.State.PLAYING)

            # Run until capturing is False
            while self.capturing:
                time.sleep(0.01)

            # Stop pipeline
            self.pipeline.set_state(Gst.State.NULL)

        except Exception as e:
            print(f"Pipeline error: {e}")
            self.capturing = False

    def start(self):
        """Start capturing via PipeWire."""
        self.frames = []
        self.capturing = True

        # Run pipeline in background thread
        self.thread = threading.Thread(target=self._run_pipeline, daemon=True)
        self.thread.start()

        print(f"PipeWire capture started: {self.fps} fps")
        print("Select the screen/window in the portal dialog!")

    def stop(self):
        """Stop capturing and return frames."""
        self.capturing = False
        if self.thread:
            self.thread.join(timeout=5)

        print(f"PipeWire capture stopped. Total frames: {len(self.frames)}")
        return self.frames.copy()

    def get_frame_count(self) -> int:
        return len(self.frames)


class SpectacleCapture:
    """Fallback capture using Spectacle (slow but reliable)."""

    # Maximum RAM usage in bytes (4GB)
    MAX_RAM_BYTES = 4 * 1024 * 1024 * 1024

    def __init__(self, region: QRect, fps: int = 20, on_memory_full=None):
        self.region = region
        self.fps = fps
        self.interval = 1.0 / fps
        self.frames = []
        self.capturing = False
        self.thread = None
        self.on_memory_full = on_memory_full  # Callback when memory limit hit
        self.current_memory = 0

    def _capture_frame(self) -> np.ndarray:
        """Capture single frame using Spectacle."""
        temp_file = f"/tmp/wayyasnitch_{time.time_ns()}.png"

        try:
            result = subprocess.run(
                ['spectacle', '-b', '-n', '-f', '-o', temp_file],
                capture_output=True,
                timeout=2
            )

            if result.returncode != 0 or not os.path.exists(temp_file):
                return None

            img = Image.open(temp_file)
            x, y, w, h = self.region.x(), self.region.y(), self.region.width(), self.region.height()
            img = img.crop((x, y, x + w, y + h))

            arr = np.array(img)
            if len(arr.shape) == 3 and arr.shape[2] == 4:
                arr = arr[:, :, :3]
            arr = arr[:, :, ::-1].copy()

            os.unlink(temp_file)
            return arr

        except Exception as e:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return None

    def _capture_loop(self):
        """Main capture loop."""
        next_frame_time = time.time()
        frames_this_second = 0
        last_second = time.time()

        while self.capturing:
            current_time = time.time()

            if current_time >= next_frame_time:
                frame = self._capture_frame()

                if frame is not None:
                    self.frames.append(frame)
                    frames_this_second += 1

                    # Track memory usage (estimate: width * height * 3 bytes per frame)
                    frame_size = frame.nbytes
                    self.current_memory += frame_size

                    # Check memory limit (4GB)
                    if self.current_memory >= self.MAX_RAM_BYTES:
                        print(f"Memory limit ({self.MAX_RAM_BYTES / (1024**3):.1f}GB) reached, auto-stitching...")
                        self.capturing = False
                        if self.on_memory_full:
                            self.on_memory_full()  # Trigger stitching callback
                        break

                next_frame_time += self.interval

                # Log FPS every second
                if current_time - last_second >= 1.0:
                    print(f"Capture rate: {frames_this_second} fps, total: {len(self.frames)}")
                    frames_this_second = 0
                    last_second = current_time

                # Skip frames if behind
                if current_time > next_frame_time + self.interval * 3:
                    while current_time > next_frame_time:
                        next_frame_time += self.interval
            else:
                sleep_time = min(0.01, next_frame_time - current_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def start(self):
        self.frames = []
        self.capturing = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"Spectacle capture started (slow ~4fps)")

    def stop(self):
        self.capturing = False
        if self.thread:
            self.thread.join(timeout=3)
        print(f"Spectacle capture stopped. Total frames: {len(self.frames)}")
        return self.frames.copy()

    def get_frame_count(self) -> int:
        return len(self.frames)


# Use fast PipeWire capture when available, fallback to Spectacle
if HAS_PIPEWIRE_CAPTURE:
    from .pipewire_fast import PipeWireFastCapture
    TimerCapture = PipeWireFastCapture
    print("Using fast PipeWire capture (~20-30 fps)")
else:
    TimerCapture = SpectacleCapture
    print("Using Spectacle capture (~4 fps on KDE Wayland)")


if __name__ == "__main__":
    print("Testing capture methods...")
    print(f"Has GStreamer: {HAS_GSTREAMER}")
