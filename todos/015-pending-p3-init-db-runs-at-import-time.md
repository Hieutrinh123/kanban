---
name: init_db() called at module import time breaks testability
description: database.init_db() at main.py:16 runs on import, creating/connecting to kanban.db in any test that imports main
type: p3
status: pending
priority: p3
issue_id: "015"
tags: [code-review, quality, testability]
---

## Problem Statement

`main.py:16` calls `database.init_db()` at module scope. Any test that imports the `main` module will immediately attempt to create or connect to `kanban.db` in the current directory. This makes the app untestable in isolation.

The modern FastAPI pattern is to use the `lifespan` context manager:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield

app = FastAPI(title="Kanban Board", lifespan=lifespan)
```

## Proposed Solutions

### Option A: Move to FastAPI lifespan handler (Recommended)
Wraps startup logic in the proper FastAPI lifecycle event. Works with `TestClient` for isolation.

**Effort:** Small | **Risk:** Very Low

## Acceptance Criteria
- [ ] `database.init_db()` not called at module scope
- [ ] Database initialized in a FastAPI `lifespan` event handler
- [ ] Tests can import `main` without side effects

## Work Log
- 2026-03-20: Identified by kieran-python-reviewer agent
