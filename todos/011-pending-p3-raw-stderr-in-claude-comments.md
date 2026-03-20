---
name: Raw subprocess stderr exposed in rendered comments
description: Claude error output (including potential API keys, file paths) written directly to comments table and rendered in UI
type: p3
status: pending
priority: p3
issue_id: "011"
tags: [code-review, security, quality]
---

## Problem Statement

`claude_reply` (`main.py:700-704`) and `process_pending_claude` write raw subprocess stderr and Python exception strings directly to the comments table:

```python
reply_text = stdout.decode().strip() if proc.returncode == 0 else f"⚠️ {stderr.decode().strip()}"
except Exception as e:
    reply_text = f"⚠️ {e}"
```

`stderr` from the Claude CLI may include API keys, authentication tokens, file paths, or internal error details. These are then persisted to the DB and rendered in the browser for all users.

## Proposed Solutions

### Option A: Log stderr server-side, show generic message in comment (Recommended)
```python
import logging
logger = logging.getLogger(__name__)

if proc.returncode != 0:
    logger.error("Claude subprocess failed: %s", stderr.decode())
    reply_text = "⚠️ Claude could not respond. Check server logs."
```

**Effort:** Small | **Risk:** Very Low

## Acceptance Criteria
- [ ] No raw subprocess stderr written to the comments table
- [ ] Full error details logged server-side with `logging.error` or `logging.exception`
- [ ] Generic user-facing message shown in comment on failure

## Work Log
- 2026-03-20: Identified by security-sentinel agent
