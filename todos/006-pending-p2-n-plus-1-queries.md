---
name: N+1 query patterns in get_data and get_board endpoints
description: Per-card and per-checklist queries in nested loops; get_board issues per-column queries with correlated subqueries
type: p2
status: pending
priority: p2
issue_id: "006"
tags: [code-review, performance, database]
---

## Problem Statement

Two endpoints have significant N+1 query patterns:

**`GET /data` (main.py:49-97):** For each card, runs separate queries for checklists, checklist items (per checklist), top-level comments, and replies (per comment). A board with 50 cards, 2 checklists, 3 comments each = **350+ queries per request**.

**`GET /api/board` (main.py:346-374):** Loops over each column and issues a separate card query per column. Each card query contains 3 correlated subqueries (total_items, completed_items, comment_count). For 4 columns × 10 cards = ~125 subquery executions.

## Findings

- `main.py:55-79`: Nested loops: cards → checklists → items + cards → comments → replies
- `main.py:350-369`: Per-column loop with correlated subquery per card
- `main.py:659-675`: `_build_claude_prompt` also has its own checklist N+1

## Proposed Solutions

### Option A: Bulk fetch + Python grouping for get_board (Recommended first step)
Replace per-column loop with a single query fetching all non-archived cards, group in Python:

```sql
SELECT c.*,
    COUNT(DISTINCT ci.id) AS total_items,
    SUM(ci.completed) AS completed_items,
    COUNT(DISTINCT cm.id) AS comment_count
FROM cards c
LEFT JOIN checklists cl ON cl.card_id = c.id
LEFT JOIN checklist_items ci ON ci.checklist_id = cl.id
LEFT JOIN comments cm ON cm.card_id = c.id
WHERE c.archived = 0
GROUP BY c.id
ORDER BY c.column_id, c.position
```

**Effort:** Medium | **Risk:** Low

### Option B: Delete /data endpoint entirely
Since the new frontend doesn't use it, deleting the `/data` endpoint (tracked in todo 001) also eliminates the worst N+1 pattern.

**Effort:** Small (as part of 001) | **Risk:** Low

## Acceptance Criteria
- [ ] `get_board()` uses a single query instead of per-column loop
- [ ] Card detail fetch (`get_card_full`) uses at most 3 queries (card, checklists+items joined, comments)
- [ ] No correlated subqueries in board load

## Work Log
- 2026-03-20: Identified by performance-oracle and kieran-python-reviewer agents
