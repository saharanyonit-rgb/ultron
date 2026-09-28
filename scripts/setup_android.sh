#!/bin/bash
# ULTRON Android/Termux Setup — Full Phone Control
# Run this in Termux to set up ULTRON with full Android phone control.
#
# Prerequisites (install from F-Droid, NOT Google Play):
#   1. Termux           — https://f-droid.org/en/packages/com.termux/
#   2. Termux:API       — https://f-droid.org/en/packages/com.termux.api/
#   3. Termux:Boot      — https://f-droid.org/en/packages/com.termux.boot/
#
# Usage:
#   chmod +x setup_android.sh
#   ./setup_android.sh

set -e

echo "=========================================="
echo "  ULTRON — Android Full Control Setup"
echo "=========================================="
echo ""

# Step 1: Update Termux packages
echo "[1/8] Updating Termux packages..."
pkg update -y && pkg upgrade -y

# Step 2: Install core packages
echo ""
echo "[2/8] Installing core packages..."
pkg install -y python git xclip espeak tmux curl wget

# Step 3: Install Termux:API and dependencies
echo ""
echo "[3/8] Installing Termux API and phone control packages..."
pkg install -y termux-api termux-tools

# Step 4: Grant storage permission (required for file access, screenshots)
echo ""
echo "[4/8] Requesting storage permission..."
termux-setup-storage 2>/dev/null || echo "  (termux-setup-storage will run on first use)"

# Step 5: Check Python version
echo ""
echo "[5/8] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 12 ]; then
    echo "  Python $PYTHON_VERSION — OK"
else
    echo "  WARNING: Python $PYTHON_VERSION detected. ULTRON requires Python 3.12+"
    echo "  Attempting to install Python 3.12..."
    pkg install -y python3.12 || echo "  Could not install Python 3.12. Current version may work for basic features."
fi

# Step 6: Clone or update the repository
echo ""
echo "[6/8] Setting up ULTRON..."
if [ -d "ultron" ]; then
    echo "  ULTRON directory found. Pulling latest..."
    cd ultron && git pull && cd ..
else
    echo "  Cloning ULTRON repository..."
    git clone https://github.com/saharanyonit-rgb/ultron.git
fi

cd ultron

# Step 7: Create virtual environment and install dependencies
echo ""
echo "[7/8] Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"

# Install Android extras
pip install httpx google-genai speechrecognition pyttsx3 pyautogui 2>/dev/null || true

# Step 8: Configure
echo ""
echo "[8/8] Configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  IMPORTANT: Edit .env to add your API key:"
    echo "    nano .env"
    echo ""
    echo "  Required settings:"
    echo "    ULTRON_PROVIDER=gemini"
    echo "    GEMINI_API_KEY=your_key_here"
    echo ""
    echo "  Get a free Gemini API key at:"
    echo "    https://aistudio.google.com/app/apikey"
else
    echo "  .env already exists — skipping."
fi

# Setup auto-start service (requires Termux:Boot)
echo ""
echo "Setting up auto-start service..."
mkdir -p ~/.termux/boot
cp ultron/scripts/android_service.sh ~/.termux/boot/ 2>/dev/null || true
chmod +x ~/.termux/boot/android_service.sh 2>/dev/null || true
echo "  Auto-start configured (requires Termux:Boot app)"

# Create working directories
mkdir -p ~/Pictures/ultron
mkdir -p ~/Documents/ultron
mkdir -p ~/.ultron

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "  AVAILABLE CONTROLS:"
echo "    - Phone: call, answer, hangup, call log"
echo "    - SMS: send, read, list messages"
echo "    - Contacts: list, search, add, delete"
echo "    - Alarms: set, list, cancel, timer"
echo "    - Notifications: send, read, dismiss"
echo "    - Settings: WiFi, Bluetooth, airplane, brightness, volume, DND"
echo "    - Device: info, storage, memory, location, network, installed apps"
echo "    - Media: play, pause, skip, volume, info"
echo "    - Touch: tap, swipe, long-press, double-tap, drag, text input"
echo "    - Navigation: back, home, recent, custom keys"
echo "    - Screen: resolution, UI dump, element click, screen reader (AI vision)"
echo "    - System: vibrate, toast, screenshots, voice (TTS/STT)"
echo ""
echo "  TO START ULTRON:"
echo "    cd ultron"
echo "    source .venv/bin/activate"
echo "    python -m ultron --lan --port 8080"
echo ""
echo "  ACCESS THE DASHBOARD:"
echo "    http://localhost:8080"
echo ""
echo "  BACKGROUND SERVICE (auto-start on boot):"
echo "    Install Termux:Boot from F-Droid"
echo "    Then restart Termux — ULTRON will auto-start"
echo ""
echo "  MANUAL SERVICE START:"
echo "    ~/ultron/scripts/android_service.sh"
echo ""
echo "  QUICK TEST:"
echo "    python -c \"from ultron.tools import ToolRegistry; r = ToolRegistry(); print(f'{len(r.all())} tools loaded')\""
echo ""
