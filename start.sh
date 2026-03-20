#!/usr/bin/env bash
# Run from the kanban directory
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt -q
python3 -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
