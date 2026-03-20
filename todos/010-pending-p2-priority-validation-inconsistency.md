---
name: Priority validation inconsistency — "none" silently coerced to "medium" in legacy sync path
description: CardCreate defaults priority to "none" but _sync_to_db coerces values not in (low/medium/high) to "medium", causing silent mutation
type: p2
status: pending
priority: p2
issue_id: "010"
tags: [code-review, quality, data-integrity]
---

## Problem Statement

Two layers validate priority with incompatible rules:

- `CardCreate` (`main.py:268`): `priority: str = "none"` — allows `"none"` as a valid value
- `database.py:31`: schema default is `'none'`
- `_sync_to_db` (`main.py:121-122`): `if priority not in ("low", "medium", "high"): priority = "medium"` — coerces `"none"` to `"medium"`

A card created via the new REST API with `priority="none"` gets stored correctly. But if that card ever flows through the legacy `/data` sync, it becomes `priority="medium"` silently.

Additionally, `CardCreate` does not validate that `priority` is one of the four allowed values, so `priority="critical"` would be accepted and stored.

## Findings

- `main.py:268`: `priority: str = "none"` — no validation
- `main.py:121-122`: `if priority not in ("low", "medium", "high"): priority = "medium"`
- `database.py:31`: `priority TEXT NOT NULL DEFAULT 'none'`

## Proposed Solutions

### Option A: Use Literal type in all Pydantic models (Recommended)
```python
from typing import Literal
Priority = Literal["none", "low", "medium", "high"]

class CardCreate(BaseModel):
    priority: Priority = "none"

class CardUpdate(BaseModel):
    priority: Optional[Priority] = None
```

Remove the runtime coercion in `_sync_to_db` or make it consistent with the Literal set.

**Effort:** Small | **Risk:** Low

## Acceptance Criteria
- [ ] `priority` validated at API boundary to one of four values: none/low/medium/high
- [ ] No silent coercion to a different priority value anywhere in the codebase
- [ ] Existing cards with `priority="none"` remain unchanged

## Work Log
- 2026-03-20: Identified by kieran-python-reviewer agent
