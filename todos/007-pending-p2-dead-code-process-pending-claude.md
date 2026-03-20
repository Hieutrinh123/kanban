---
name: Dead code — process_pending_claude and legacy /data Claude path
description: process_pending_claude and the SSE comment stream are never called by the current frontend; diverge from live claude_reply behavior
type: p2
status: pending
priority: p2
issue_id: "007"
tags: [code-review, architecture, maintainability]
---

## Problem Statement

`process_pending_claude` (`main.py:198-258`) is only triggered from `POST /data`, which the current frontend never calls. The live Claude path is `claude_reply` (`main.py:688-718`), triggered from `POST /api/cards/{id}/comments`.

The two functions have divergent behavior that misleads developers:
- `process_pending_claude`: opens 3 separate DB connections, uses streaming chunk writes, inserts "thinking" placeholder
- `claude_reply`: uses `proc.communicate()` (single write), no placeholder, single connection

ARCHITECTURE.md documents `process_pending_claude` as the active flow.

## Findings

- `main.py:198-258`: `process_pending_claude` — ~60 lines, only called from `POST /data`
- `main.py:100-107`: `POST /data` route — only caller of `process_pending_claude`
- `main.py:688-718`: `claude_reply` — the live active function
- ARCHITECTURE.md lines 122-128: Documents old flow as active

## Proposed Solutions

### Option A: Delete both functions together with /data cleanup (Recommended)
As part of todo 001, remove `process_pending_claude` along with `POST /data`. ~60 additional lines removed.

**Effort:** Small (as part of 001) | **Risk:** Low

### Option B: Port streaming behavior from process_pending_claude into claude_reply
If live streaming is desired, extract the "thinking" placeholder + chunk-write pattern from the old function and wire it into `claude_reply` + the SSE stream endpoint.

**Effort:** Large | **Risk:** Medium

## Acceptance Criteria
- [ ] `process_pending_claude` removed or the streaming behavior ported to `claude_reply`
- [ ] Single authoritative Claude integration path in the codebase
- [ ] ARCHITECTURE.md reflects the live flow

## Work Log
- 2026-03-20: Identified by architecture-strategist and kieran-python-reviewer agents
