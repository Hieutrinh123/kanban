---
name: Missing type annotations and legacy typing usage throughout main.py
description: Internal functions lack return types; mixed use of typing.List/Optional with modern list/str|None forms
type: p3
status: pending
priority: p3
issue_id: "014"
tags: [code-review, quality, type-safety]
---

## Problem Statement

Multiple internal functions in `main.py` lack type annotations, making static analysis (mypy/pyright) less effective:

- `_ts(dt_str: str)` — missing `-> int`
- `_dt(ts_ms)` — `ts_ms` untyped, missing `-> str`
- `_try_int(val)` — `val` untyped, missing `-> int | None`
- `get_card_full(conn, card_id: int)` — `conn` untyped, return is `dict | None` but not annotated
- `_sync_to_db`, `_sync_subtasks`, `_sync_comments` — `conn` untyped, missing `-> None`
- `claude_reply`, `_build_claude_prompt` — missing return types

Also: Pydantic models use legacy `List[int]`, `Optional[str]` from `typing` module, while `from __future__ import annotations` is already imported. Modern syntax is `list[int]` and `str | None`.

`get_db()` in `database.py` also lacks `-> sqlite3.Connection`.

## Proposed Solutions

### Option A: Add annotations incrementally during normal development
Fix annotations when touching each function for other reasons. Low-risk, no behavior change.

### Option B: Batch cleanup in one PR
Add all missing annotations and replace `typing.List`/`Optional` with modern forms throughout.

**Effort:** Small | **Risk:** Very Low

## Acceptance Criteria
- [ ] All functions in `main.py` have parameter and return type annotations
- [ ] `get_db()` annotated as `-> sqlite3.Connection`
- [ ] No legacy `typing.List`, `typing.Optional` — use `list[...]`, `... | None`
- [ ] `from typing import List, Optional` imports removed

## Work Log
- 2026-03-20: Identified by kieran-python-reviewer agent
