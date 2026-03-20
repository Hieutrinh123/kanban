@echo off
cd /d "%~dp0"
echo.
echo [Kanban] Checking dependencies...
python -m pip install fastapi uvicorn pydantic -q

echo [Kanban] Starting server at http://localhost:8000...
start "" "http://localhost:8000"
python -m uvicorn main:app --host 127.0.0.1 --port 8000

if %ERRORLEVEL% neq 0 (
    echo.
    echo [Kanban] ERROR: Server failed to start.
    echo Please check if port 8000 is occupied or if Python is installed.
    pause
)
