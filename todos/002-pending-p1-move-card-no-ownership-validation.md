---
name: move_card updates arbitrary card IDs with no ownership check
description: /api/cards/{id}/move endpoint accepts source_ids and target_ids without verifying they belong to the claimed columns
type: p1
status: pending
priority: p1
issue_id: "002"
tags: [code-review, security, architecture]
---

## Problem Statement

The `move_card` endpoint (`main.py:439-453`) accepts `source_ids: List[int]` and `target_ids: List[int]` from the request body and blindly updates ALL card IDs in those lists — with no verification that they belong to the claimed source/target columns. The `card_id` URL path parameter is accepted but **never used in any SQL query**.

Any caller can craft a request to reassign arbitrary cards to arbitrary columns, or reorder cards in columns they never touched.

## Findings

- `main.py:439-453`: `for pos, cid in enumerate(body.source_ids): conn.execute("UPDATE cards SET position=? WHERE id=?", (pos, cid))`
- `main.py:445-449`: `UPDATE cards SET column_id=?, position=? WHERE id=?` applied to all `target_ids` unconditionally
- `card_id` path parameter is declared but never referenced in any SQL
- No 404 if `card_id` doesn't exist

## Proposed Solutions

### Option A: Validate ownership before batch update (Recommended)
Before executing updates, query the DB to verify all IDs in `source_ids` have `column_id = source_column_id`, and all in `target_ids` have `column_id` equal to either source or target column. Raise HTTP 422 on mismatch.

```python
src_rows = conn.execute(
    f"SELECT id FROM cards WHERE id IN ({','.join('?'*len(body.source_ids))}) AND column_id=?",
    (*body.source_ids, body.source_column_id)
).fetchall()
if len(src_rows) != len(set(body.source_ids)):
    raise HTTPException(422, "source_ids contains cards not in source column")
```

**Pros:** Enforces server-side integrity, simple fix
**Cons:** Adds 2-3 extra queries per move
**Effort:** Small | **Risk:** Low

### Option B: Use card_id as the sole card being moved; derive column membership from DB
Ignore `source_ids`/`target_ids` for membership validation — fetch them from the DB by column_id.

**Pros:** More robust
**Cons:** Larger refactor
**Effort:** Medium | **Risk:** Low

## Acceptance Criteria
- [ ] `move_card` validates all card IDs in source_ids belong to source column
- [ ] `move_card` validates all card IDs in target_ids belong to source or target column
- [ ] HTTP 422 returned for invalid card ID lists
- [ ] `card_id` path param is either used or endpoint signature updated

## Work Log
- 2026-03-20: Identified by security-sentinel and architecture-strategist agents
