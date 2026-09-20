@echo off
setlocal
title YojanSetu (योजनसेतु) - Launcher
cd /d "%~dp0"

echo ========================================================================
echo    YOJANSETU (योजनसेतु) - Government Scheme Assistant Launcher
echo    Offline-First Vernacular ReAct Agent & Citizen Welfare Platform
echo ========================================================================
echo.

:: 1. Verify Python Virtual Environment
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
    echo [!] ERROR: Python virtual environment not found at:
    echo     %~dp0backend\.venv\Scripts\python.exe
    echo.
    echo Please make sure the backend virtual environment is created.
    pause
    exit /b 1
)

echo [*] Starting Backend API Server (FastAPI on http://127.0.0.1:8000)...
start "YojanSetu - Backend API (:8000)" cmd /k "cd /d ""%~dp0backend"" && "".venv\Scripts\python.exe"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [*] Starting Frontend Application (Next.js on http://localhost:3000)...
start "YojanSetu - Frontend Web (:3000)" cmd /k "set NODE_OPTIONS=--max-old-space-size=4096 && cd /d ""%~dp0frontend"" && npm run dev"

echo.
echo [*] Waiting 5 seconds for servers to initialize...
timeout /t 5 /nobreak >nul

echo [*] Opening Citizen Assistant in default web browser...
start http://localhost:3000/citizen

echo.
echo ========================================================================
echo   YOJANSETU IS RUNNING!
echo ========================================================================
echo   * Citizen Discovery Portal : http://localhost:3000/citizen
echo   * Live Eligibility Tool    : http://localhost:3000/citizen (Simulator)
echo   * Admin Control Center     : http://localhost:3000/admin
echo   * Interactive API Swagger  : http://127.0.0.1:8000/docs
echo ========================================================================
echo.
echo Tip: Keep this launcher and the opened console windows open while using.
echo To stop the application, simply close the console windows.
echo.
pause
exit /b 0
