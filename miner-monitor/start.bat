@echo off
title Miner Monitor
color 0B
cd /d "%~dp0"
echo.
echo  ==========================================
echo   MINER MONITOR
echo   Frontend : http://localhost:5001
echo   Backend  : http://localhost:5002
echo  ==========================================
echo.

python --version >nul 2>&1 || (echo ERROR: Python not installed. Get it at python.org & pause & exit /b 1)
node   --version >nul 2>&1 || (echo ERROR: Node.js not installed. Get it at nodejs.org  & pause & exit /b 1)

if not exist "backend\.venv\Scripts\python.exe" (
    echo [1/4] Creating Python environment...
    python -m venv backend\.venv
)

echo [2/4] Installing Python packages...
(
echo fastapi==0.115.0
echo uvicorn[standard]==0.32.0
echo sqlalchemy==2.0.36
echo aiosqlite==0.20.0
echo apscheduler==3.10.4
echo scikit-learn==1.5.2
echo numpy==2.1.3
echo pandas==2.2.3
echo httpx==0.27.2
echo python-multipart==0.0.12
echo pydantic==2.9.2
echo pydantic-settings==2.6.1
echo python-dotenv==1.0.1
echo websockets==13.1
echo greenlet==3.1.1
echo openpyxl==3.1.2
) > backend\requirements.txt

backend\.venv\Scripts\pip install --only-binary=:all: -q -r backend\requirements.txt 2>nul
if errorlevel 1 backend\.venv\Scripts\pip install -q -r backend\requirements.txt

echo [3/4] Installing Node packages...
if not exist "frontend\node_modules" (
    cd frontend & npm install --silent & cd ..
)

if not exist "backend\data"         mkdir backend\data
if not exist "backend\data\models"  mkdir backend\data\models
if not exist "backend\presets"      mkdir backend\presets

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /r "IPv4.*[0-9]"') do (set R=%%a & goto :ip)
:ip
set LIP=%R: =%

echo [4/4] Starting...
echo.
echo  ============================================================
echo   Dashboard : http://localhost:5001
echo   Network   : http://%LIP%:5001
echo   API docs  : http://localhost:5002/docs
echo   Data dir  : %~dp0backend\data
echo.
echo   CHATBOT SETUP (Gemini - free, no credit card):
echo   1. Go to: https://aistudio.google.com/apikey
echo   2. Create a free API key
echo   3. Set it: set GEMINI_API_KEY=your_key_here
echo      OR save to: backend\data\gemini_key.txt
echo   4. Restart this script
echo  ============================================================
echo.

start "Miner Monitor Backend"  cmd /k "cd /d %~dp0 && set PYTHONPATH=. && backend\.venv\Scripts\uvicorn backend.api.main:app --host 0.0.0.0 --port 5002 --reload"
timeout /t 5 /nobreak >nul
start "Miner Monitor Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"
timeout /t 5 /nobreak >nul
start http://localhost:5001
pause
