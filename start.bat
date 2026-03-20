@echo off
cd /d "%~dp0"
start "" "http://localhost:3000"
"C:\Users\hieutc12\python-3.12.10\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 3000
