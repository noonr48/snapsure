# SnapSure (WayYaSnitch)

A screen capture and stitching tool for **KDE Plasma Wayland** on Linux. Captures screen regions while you scroll and stitches them into a single tall image/PDF.

## Why?

Some websites (like university portals) restrict PDF downloads or use scroll-based viewers that prevent saving. SnapSure captures the content pixel-by-pixel as you scroll and stitches it into one complete document.

## Features

- **System tray app** - Green "S" icon when idle, red when recording
- **Region selection** - Drag to select capture area with green overlay
- **Auto-stitching** - NCC template matching to detect overlapping regions
- **4GB RAM limit** - Auto-stops and stitches when limit reached
- **Multiple outputs** - Saves both PDF and PNG to Desktop
- **CPU-only** - No GPU acceleration required, works on any x86_64 processor

## Requirements

- KDE Plasma Wayland
- Python 3.8+
- Spectacle (KDE screenshot tool)

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

# Run
python main.py
```

## Usage

1. **Start the app** - A green "S" icon appears in your system tray
2. **Click the tray icon** - Screen dims and a green overlay appears
3. **Drag to select region** - Draw a rectangle around the content you want to capture
4. **Scroll slowly** - The app captures ~4fps while you scroll down
5. **Click tray icon again** - Stops capture and starts stitching
6. **Check Desktop** - PDF and PNG files are saved automatically

### Tips for Best Results

- **Scroll slowly and steadily** - Fast scrolling causes gaps
- **Keep consistent speed** - Helps overlap detection
- **Watch the tray icon** - Red "S" means recording is active
- **Long documents** - App auto-stops at 4GB RAM usage and stitches automatically

## Project Structure

```
snapsure/
├── main.py                 # Main app, tray icon, state machine
├── capture/
│   ├── qt_capture.py       # Spectacle-based screen capture
│   └── selection.py        # Region selection overlay
├── stitch/
│   └── matcher.py          # NCC template matching for stitching
├── output/
│   └── pdf_generator.py    # PDF/PNG generation
├── utils/
│   └── notifications.py    # Desktop notifications
└── config/
    └── settings.py         # App settings
```

## Known Issues

- **Overlap detection needs improvement** - Frames may not align perfectly
- **~4fps capture limit** - Spectacle is slower than direct PipeWire capture
- **Wayland limitations** - Standard hotkeys don't work (using tray icon instead)

## Technical Details

### Screen Capture

Uses KDE's Spectacle CLI tool (`spectacle -b -n -f -o`) because:
- Qt's `grabWindow()` returns black frames on Wayland
- `grim` requires wlroots (not available on KDE)
- Direct PipeWire capture requires complex xdg-desktop-portal session setup

### Image Stitching

Uses Normalized Cross-Correlation (NCC) template matching:
1. Takes bottom portion of previous frame as template
2. Searches for match in top portion of current frame
3. Validates with pixel-level similarity check
4. Stacks non-overlapping portions vertically

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
```

## License

MIT

## Contributing

PRs welcome! Key areas for improvement:
- Better overlap detection algorithm
- Faster capture method (PipeWire integration)
- Support for other Wayland compositors
