#!/usr/bin/env bash
# Run from the kanban directory
PYTHON="/c/Users/hieutc12/python-3.12.10/python.exe"
cd "$(dirname "$0")"
$PYTHON -m pip install -r requirements.txt -q
$PYTHON -m uvicorn main:app --reload --host 127.0.0.1 --port 3000
