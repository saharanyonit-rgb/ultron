#!/bin/bash
# ULTRON Android Background Service
# Auto-start daemon for full phone control.
#
# Installation:
#   termux-setup-storage
#   mkdir -p ~/.termux/boot/
#   cp android_service.sh ~/.termux/boot/
#   chmod +x ~/.termux/boot/android_service.sh
#   pkg install termux-boot
#
# Requirements:
#   - Termux:Boot app from F-Droid
#   - Termux:API app from F-Droid
#   - termux-api package installed

set -e

ULTRON_DIR="$HOME/ultron"
LOG_FILE="$HOME/.ultron/service.log"
PID_FILE="$HOME/.ultron/service.pid"

mkdir -p "$HOME/.ultron"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ULTRON service starting..." >> "$LOG_FILE"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ULTRON already running (PID $OLD_PID)" >> "$LOG_FILE"
        exit 0
    fi
fi

# Change to ULTRON directory
cd "$ULTRON_DIR" || {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: ULTRON directory not found: $ULTRON_DIR" >> "$LOG_FILE"
    exit 1
}

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: .venv not found. Run setup_android.sh first." >> "$LOG_FILE"
    exit 1
fi

# Start ULTRON in background with full Android control
nohup python -m ultron --headless --lan --port 8080 \
    >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ULTRON started (PID $!)" >> "$LOG_FILE"

# Wait a moment and verify it started
sleep 3
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ULTRON service running successfully" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: ULTRON may have failed to start" >> "$LOG_FILE"
    cat "$LOG_FILE" | tail -20
fi
