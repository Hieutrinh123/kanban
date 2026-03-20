---
name: Missing database indexes on all foreign key and filter columns
description: Schema has zero explicit indexes beyond PKs; all joins and WHERE clauses do full table scans
type: p2
status: pending
priority: p2
issue_id: "005"
tags: [code-review, performance, database]
---

## Problem Statement

`database.py` defines 5 tables with no explicit indexes. Every query that filters or joins on a non-PK column performs a full table scan. With board growth, this degrades all read endpoints.

Most-impacted queries:
- `cards WHERE column_id=? AND archived=0` — runs for every column in `get_board()`
- `checklists WHERE card_id=?` — runs for every card detail fetch
- `checklist_items WHERE checklist_id=?` — runs for every checklist
- `comments WHERE card_id=?` — runs for every card detail and comment list
- `comments WHERE reply_to_id=?` — runs for every top-level comment in legacy /data

## Findings

- `database.py:15-66`: No `CREATE INDEX` statements
- `main.py:354-369`: Per-column card query with `WHERE c.column_id = ? AND c.archived = 0`
- `main.py:324-335`: `get_card_full` queries checklists, items, comments separately

## Proposed Solutions

### Option A: Add indexes in init_db() (Recommended)
Add after the CREATE TABLE block in `init_db()`:

```sql
CREATE INDEX IF NOT EXISTS idx_cards_column_archived ON cards(column_id, archived);
CREATE INDEX IF NOT EXISTS idx_checklists_card_id ON checklists(card_id);
CREATE INDEX IF NOT EXISTS idx_checklist_items_checklist_id ON checklist_items(checklist_id);
CREATE INDEX IF NOT EXISTS idx_comments_card_id ON comments(card_id);
CREATE INDEX IF NOT EXISTS idx_comments_reply_to_id ON comments(reply_to_id);
```

`IF NOT EXISTS` makes this safe to add to the existing init_db for upgrade scenarios.

**Pros:** Zero behavior change, immediate query speedup, backward compatible
**Effort:** Small | **Risk:** Very Low

## Acceptance Criteria
- [ ] Compound index on `cards(column_id, archived)` exists
- [ ] Index on `checklists(card_id)` exists
- [ ] Index on `checklist_items(checklist_id)` exists
- [ ] Index on `comments(card_id)` exists
- [ ] Index on `comments(reply_to_id)` exists
- [ ] Existing databases upgraded without data loss on next startup

## Work Log
- 2026-03-20: Identified by performance-oracle agent
