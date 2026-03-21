# Kanban Project — Claude Instructions

## After implementing any feature or fix

Always restart the server so the user is ready to test immediately.

Use this command to restart:
```
taskkill //F //IM python.exe 2>/dev/null; /c/Users/hieutc12/python-3.12.10/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 > server.log 2>&1 &
```

Then confirm it's running before telling the user to test.
