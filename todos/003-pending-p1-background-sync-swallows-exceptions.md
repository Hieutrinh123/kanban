---
name: Background sync silently swallows all exceptions
description: _sync_to_db runs as a background task, catches all exceptions with only a print(), returns ok:true to client even on failure
type: p1
status: pending
priority: p1
issue_id: "003"
tags: [code-review, reliability, data-integrity]
---

## Problem Statement

`_sync_to_db` is scheduled as a `BackgroundTask` from `POST /data`. The entire function body is wrapped in `except Exception as e: print(f"[sync error] {e}")`. This means:

1. The client always receives `{"ok": True}` even when the sync failed
2. Card deletions, upserts, and comment syncs may have partially executed before the error
3. The database may be in an inconsistent partial state with no way to detect it
4. Only a print statement (not structured logging) captures the error

## Findings

- `main.py:147-148`: `except Exception as e: print(f"[sync error] {e}")`
- `main.py:101-107`: Endpoint schedules `_sync_to_db` as background task, immediately returns `{"ok": True}`
- No rollback on partial failure (conn.commit() only called on success path)

## Proposed Solutions

### Option A: Add proper logging + make error visible in UI (Recommended)
Replace `print` with `logging.exception` to capture full tracebacks. Since this is a background task, expose a `/api/sync-status` endpoint or include last error in the health check.

**Pros:** Immediate improvement with minimal change
**Effort:** Small | **Risk:** Low

### Option B: Move sync logic to synchronous endpoint
Convert `POST /data` to a synchronous endpoint that returns the actual error to the client.

**Pros:** Client gets real error feedback
**Cons:** Blocks response until sync completes
**Effort:** Small | **Risk:** Low

## Acceptance Criteria
- [ ] Sync errors logged with full traceback via `logging.exception`
- [ ] Client can detect sync failures (either via error response or status endpoint)
- [ ] Database remains consistent on partial failure (transaction rollback)

## Work Log
- 2026-03-20: Identified by kieran-python-reviewer agent
