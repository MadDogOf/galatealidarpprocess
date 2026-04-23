@echo off
setlocal

echo ============================================================
echo   Galatea: Digital Wardrobe - System Bootstrapper (Windows)
echo ============================================================

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python 3 not found in PATH.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
if not exist ".venv" (
    echo [SYSTEM] Creating virtual environment...
    python -m venv .venv
)

echo [SYSTEM] Activating environment...
call .venv\Scripts\activate

:: 3. Sync Dependencies
echo [SYSTEM] Syncing dependencies (including SMPL-X)...
python -m pip install --upgrade pip -q
if exist "requirements.txt" (
    python -m pip install -r requirements.txt -q
)
python -m pip install flask flask-cors -q

:: 4. Model Check
echo [SYSTEM] Verifying SMPL-X models...
if not exist "smplx_models\models" (
    echo [!] CRITICAL: smplx_models\models not found!
    echo [!] Please ensure you have downloaded the SMPL-X models.
    echo [!] Expected structure: smplx_models\models\smplx\SMPLX_NEUTRAL.npz
)

:: 5. Launch API Server & Frontend
echo [SYSTEM] Starting Galatea API Server...
echo [SYSTEM] Dashboard will open at http://127.0.0.1:5001
start /b python api_server.py

:: Give server a moment to start before opening browser
timeout /t 2 /nobreak >nul
start http://127.0.0.1:5001

echo [SYSTEM] System is running. Close this window to stop the server.
echo.
pause
