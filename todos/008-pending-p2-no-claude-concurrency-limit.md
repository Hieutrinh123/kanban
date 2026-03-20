---
name: No concurrency limit on Claude subprocess invocations
description: Every @claude comment spawns an unbounded background subprocess; 10 rapid @claude comments = 10 concurrent claude -p processes
type: p2
status: pending
priority: p2
issue_id: "008"
tags: [code-review, reliability, performance]
---

## Problem Statement

`create_comment` (`main.py:599-616`) calls `background_tasks.add_task(claude_reply, ...)` for every comment containing `@claude`. FastAPI's `BackgroundTasks` runs all tasks after the response, in the same event loop. `claude_reply` awaits `asyncio.wait_for(..., timeout=120)` on a `claude -p` subprocess.

Ten rapid `@claude` comments = 10 concurrent subprocesses each potentially running for 2 minutes. On a laptop, this can exhaust memory and CPU, causing all Claude calls to time out simultaneously.

## Findings

- `main.py:599-616`: `background_tasks.add_task(claude_reply, ...)` with no guard
- `main.py:691-700`: `asyncio.create_subprocess_exec("claude", "-p", ...)` — one process per call
- No semaphore, queue, or rate limiting

## Proposed Solutions

### Option A: Module-level asyncio.Semaphore (Recommended)
```python
_claude_semaphore = asyncio.Semaphore(2)  # max 2 concurrent Claude calls

async def claude_reply(...):
    async with _claude_semaphore:
        proc = await asyncio.create_subprocess_exec(...)
```

**Pros:** Simple, effective, allows 1-2 concurrent calls, queues the rest
**Effort:** Small | **Risk:** Low

### Option B: Queue with a single worker
Use `asyncio.Queue` and a single background worker task to serialize Claude calls.

**Pros:** Guaranteed ordering, no parallel resource contention
**Cons:** More complex, calls queue indefinitely
**Effort:** Medium | **Risk:** Low

## Acceptance Criteria
- [ ] At most N concurrent `claude -p` subprocesses at any time (N configurable, default 2)
- [ ] Excess requests queued, not rejected
- [ ] Semaphore does not block FastAPI event loop for other requests

## Work Log
- 2026-03-20: Identified by architecture-strategist agent
