#!/bin/bash
# Galatea Stealth System - Unified Bootstrapper

echo "===================================================="
echo "  GALATEA: DIGITAL WARDROBE - BOOTING SYSTEM"
echo "===================================================="

# 1. Environment Check
if [ ! -d ".venv" ]; then
    echo "[SYSTEM] Creating virtual environment..."
    python3 -m venv .venv
fi

echo "[SYSTEM] Activating environment..."
source .venv/bin/activate

# 2. Dependency Sync
echo "[SYSTEM] Syncing dependencies (including SMPL-X)..."
python3 -m pip install --upgrade pip -q
python3 -m pip install -r requirements.txt -q
python3 -m pip install flask flask-cors -q

# 3. Model Check
echo "[SYSTEM] Verifying SMPL-X models..."
if [ ! -d "smplx_models/models" ]; then
    echo "[!] CRITICAL: smplx_models/models not found!"
    echo "[!] Please ensure you have downloaded the SMPL-X models."
    echo "[!] Expected structure: smplx_models/models/smplx/SMPLX_NEUTRAL.npz"
fi

# 4. Launch API Server & Frontend
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null ; then
    echo "[SYSTEM] Galatea Vision is already running on port 5001."
    echo "[SYSTEM] Processing will continue in your existing browser window."
else
    echo "[SYSTEM] Starting Galatea Vision API Server..."
    # Run server in background
    python3 api_server.py &
    SERVER_PID=$!
    # Wait for server to boot
    sleep 2
    echo "[SYSTEM] Launching Dashboard..."
    open "http://127.0.0.1:5001"
fi

echo "===================================================="
echo "  SYSTEM ACTIVE - Press Ctrl+C to shutdown"
echo "===================================================="

# Keep script alive and handle shutdown
trap "kill $SERVER_PID; echo 'System Offline.'; exit" INT TERM
wait $SERVER_PID
