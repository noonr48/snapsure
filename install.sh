#!/bin/bash
# WayYaSnitch Installation Script for CachyOS/Arch Linux
# CPU-only version - uses Python virtual environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== WayYaSnitch Installer ==="
echo "Installing dependencies for KDE Plasma Wayland..."

# System packages (skip if conflicts arise)
echo "[1/4] Checking system dependencies..."
sudo pacman -S --needed --noconfirm python python-pip grim slurp 2>/dev/null || true

# Create virtual environment
echo "[2/4] Creating Python virtual environment..."
python -m venv "$VENV_DIR"

# Activate and install Python packages
echo "[3/4] Installing Python dependencies into venv..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"
deactivate

# Make scripts executable
echo "[4/4] Setting up executables..."
chmod +x "$SCRIPT_DIR/main.py"
chmod +x "$SCRIPT_DIR/run.sh"

# Create run script
cat > "$SCRIPT_DIR/run.sh" << 'RUNEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/main.py" "$@"
deactivate
RUNEOF
chmod +x "$SCRIPT_DIR/run.sh"

# Create desktop entry
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/wayyasnitch.desktop << EOF
[Desktop Entry]
Name=WayYaSnitch
Comment=Screen capture and stitch tool for Wayland
Exec=$SCRIPT_DIR/run.sh
Icon=camera-video
Terminal=false
Type=Application
Categories=Graphics;Scanning;
EOF

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Virtual environment created at: $VENV_DIR"
echo ""
echo "Usage:"
echo "  Run: $SCRIPT_DIR/run.sh"
echo "  Or:  source .venv/bin/activate && python main.py"
echo ""
echo "Hotkey: CTRL+` (backtick) to start/stop capture"
echo "Output: ~/Desktop/"
