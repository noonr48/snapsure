# SnapSure (WayYaSnitch)

A screen capture and stitching tool for **Wayland** on Linux. Captures screen regions while you scroll and stitches them into a single tall image/PDF.

## Why?

Some websites (like university portals) restrict PDF downloads or use scroll-based viewers that prevent saving. SnapSure captures the content pixel-by-pixel as you scroll and stitches it into one complete document.

**Works on sites where browser extensions are blocked** - uses system-level screen capture via PipeWire.

## Features

- **System tray app** - Green "S" icon when idle, red when recording
- **PipeWire capture** - Fast screen capture on Wayland using xdg-desktop-portal
- **Window picker** - System dialog to select window/screen to capture
- **Auto-stitching** - Template matching to detect overlapping regions
- **4GB RAM limit** - Auto-stops and stitches when limit reached
- **Multiple outputs** - Saves both PDF and PNG to Desktop
- **CPU-only** - No GPU acceleration required
- **12 FPS capture** - Balanced between frame count and overlap detection

## Requirements

- Wayland (KDE Plasma, GNOME, etc.)
- Python 3.8+
- pipewire-capture library
- PyQt5

## Installation

```bash
# Clone the repo
git clone https://github.com/noonr48/snapsure.git
cd snapsure

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install pipewire-capture for Wayland support
pip install pipewire-capture

# Run
python main.py
```

## Usage

1. **Start the app** - A green "S" icon appears in your system tray
2. **Click the tray icon** - A window/monitor selection dialog appears
3. **Select a window** - Choose the window you want to capture
4. **Scroll steadily** - The app captures at 12 FPS while you scroll down
5. **Click tray icon again** - Stops capture and starts stitching
6. **Check Desktop** - PDF and PNG files are saved automatically

### Tips for Best Results

- **Scroll smoothly and steadily** - Consistent speed helps overlap detection
- **One direction only** - Scroll down without going back up
- **Moderate speed** - Not too fast (gaps) or too slow (too many similar frames)
- **Long documents** - App auto-stops at 4GB RAM usage and stitches automatically

## Project Structure

```
snapsure/
├── main.py                     # Main app, tray icon, state machine
├── capture/
│   ├── pipewire_fast.py        # PipeWire screen capture (Wayland)
│   └── qt_capture.py           # Capture method abstraction
├── stitch/
│   ├── simple_vertical.py      # Vertical scrolling stitcher
│   ├── vertical_stitcher.py    # Alternative vertical stitcher
│   └── matcher.py              # Main stitching entry point
├── output/
│   └── pdf_generator.py        # PDF/PNG generation
└── utils/
    └── notifications.py        # Desktop notifications
```

## Known Issues

- **Some frames may be skipped** - Low confidence matches are discarded to prevent misalignment
- **Occasional gaps** - Fast scrolling or dynamic content can cause missing sections
- **Bottom cutoff** - Sometimes the very end of the page isn't captured
- **Requires smooth scrolling** - Inconsistent scroll speed affects overlap detection

## Technical Details

### Screen Capture (PipeWire)

Uses `pipewire-capture` library with xdg-desktop-portal:
- **Why not Spectacle?** Slower (~4 FPS), requires region selection on Wayland
- **Why not browser automation?** University sites block programmatic scrolling
- **PipeWire advantages:**
  - Fast (20-30 FPS possible, using 12 FPS for balance)
  - System window picker dialog
  - Works on any Wayland compositor (KDE, GNOME, etc.)
  - Captures full window including browser chrome

### Image Stitching

Uses template matching with multi-strip validation:

1. **Multi-strip detection** - Tries 200px, 300px, 400px strips for robustness
2. **Overlap range** - Looks for 100-700px overlaps (reasonable for scrolling)
3. **Confidence threshold** - 0.12 (lowered for dynamic content)
4. **Duplicate detection** - 0.85 threshold to prevent back-scrolling issues
5. **Deduplication** - Only removes truly identical frames (0.5 threshold)

**Why not feature-based (SIFT/ORB)?**
- Too complex for linear scrolling
- Finds wrong matches with repeating patterns
- Browser extensions like Fullshot use position-based stitching (they control scroll)
- We can't control scroll, so we use template matching

### Stitching Algorithm

```python
# For each frame pair:
1. Find overlap using multiple strip sizes (200, 300, 400px)
2. Use best match if overlap in valid range (100-700px)
3. Check if new content already exists in result (prevent duplicates)
4. Add only non-overlapping portion to result
```

### Memory Management

- Tracks estimated memory usage per frame
- Auto-stops at 4GB to prevent system slowdown
- Triggers stitching callback when limit reached

## Dependencies

```
PyQt5>=5.15
opencv-python>=4.5
numpy>=1.20
Pillow>=8.0
img2pdf>=0.4
pipewire-capture>=0.1
```

## License

MIT

## Contributing

PRs welcome! Key areas for improvement:
- Better overlap detection for dynamic content
- Adaptive confidence thresholds
- Support for horizontal scrolling
- Multi-page document handling

## Changelog

### Current (2025-03-03)
- ✅ Added PipeWire capture support for Wayland
- ✅ Implemented multi-strip template matching
- ✅ Increased capture rate to 12 FPS
- ✅ Added duplicate content detection
- ✅ Fixed deduplication to keep valid scrolling frames
- 🔧 Ongoing: Improving overlap detection accuracy
