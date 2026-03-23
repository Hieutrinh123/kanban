@echo off
cd /d "%~dp0"
echo.

:: Find Python - try 'py' launcher first, then 'python', then 'python3'
set PYTHON=
where py >nul 2>&1 && set PYTHON=py
if "%PYTHON%"=="" where python >nul 2>&1 && set PYTHON=python
if "%PYTHON%"=="" where python3 >nul 2>&1 && set PYTHON=python3

if "%PYTHON%"=="" (
    echo [Kanban] ERROR: Python not found. Please install Python from https://python.org
    pause
    exit /b 1
)

echo [Kanban] Using: %PYTHON%
echo [Kanban] Checking dependencies...
%PYTHON% -m pip install fastapi uvicorn pydantic -q

echo [Kanban] Starting server at http://localhost:8000...
start /b %PYTHON% -m uvicorn main:app --host 127.0.0.1 --port 8000
timeout /t 3 /nobreak >nul
start "" "http://localhost:8000"
echo [Kanban] Server started. Press Ctrl+C to stop.
pause
