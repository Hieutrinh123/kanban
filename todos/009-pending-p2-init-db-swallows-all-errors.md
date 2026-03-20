---
name: init_db swallows ALL ALTER TABLE exceptions, not just duplicate-column
description: Bare except Exception: pass in database.py hides disk full, permissions errors, and schema corruption at startup
type: p2
status: pending
priority: p2
issue_id: "009"
tags: [code-review, reliability, database]
---

## Problem Statement

`database.py:69-81` wraps ALTER TABLE migration statements in `except Exception: pass`. The comment says `# column already exists`, but a bare `Exception` catch hides:
- Disk full errors
- File permission errors
- Corrupted schema
- Malformed SQL (if a future migration is added with a typo)

The application starts silently with an incomplete schema, and runtime errors appear to have no cause.

## Findings

- `database.py:77-81`:
  ```python
  try:
      conn.execute(sql)
  except Exception:
      pass  # column already exists
  ```
- SQLite raises `sqlite3.OperationalError` with message `"duplicate column name: X"` for the expected case
- All other errors are swallowed identically

## Proposed Solutions

### Option A: Catch specific error and inspect message (Recommended)
```python
import sqlite3 as _sqlite3

try:
    conn.execute(sql)
except _sqlite3.OperationalError as exc:
    if "duplicate column name" not in str(exc):
        raise
```

**Pros:** Exact fix, zero behavior change for the expected case
**Effort:** Small | **Risk:** Very Low

## Acceptance Criteria
- [ ] Only `sqlite3.OperationalError` with "duplicate column name" is suppressed
- [ ] All other exceptions during `init_db` propagate and crash startup with a clear error
- [ ] Successful ALTER TABLE statements optionally logged at DEBUG level

## Work Log
- 2026-03-20: Identified by architecture-strategist and kieran-python-reviewer agents
