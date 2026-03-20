@echo off
cd /d "%~dp0"
start "" "http://localhost:3000"
python -m uvicorn main:app --host 127.0.0.1 --port 3000
