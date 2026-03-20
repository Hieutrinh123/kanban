---
name: No field length limits on text inputs
description: title, description, comment text, assignee accept arbitrarily large strings; no due_date or priority format validation
type: p3
status: pending
priority: p3
issue_id: "013"
tags: [code-review, quality, validation]
---

## Problem Statement

Pydantic models declare plain `str` fields with no constraints. A user (or script) can POST a 1MB card title. Claude is invoked with the full card context, so oversized inputs can hit the Claude CLI's context window limit, produce unexpected billing, or cause slow rendering when loaded back.

Additionally:
- `due_date` is stored as `TEXT` with no format validation — `"not-a-date"` is accepted and stored
- `priority` has no enum validation in `CardCreate`/`CardUpdate` (tracked in todo 010)
- `column_id` in `CardCreate` is not validated against existing columns

## Proposed Solutions

### Option A: Add Field() constraints to Pydantic models (Recommended)
```python
from pydantic import Field

class CardCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field("", max_length=10000)
    assignee: Optional[str] = Field(None, max_length=100)
    due_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
```

**Effort:** Small | **Risk:** Very Low

## Acceptance Criteria
- [ ] `title` max_length enforced (e.g., 500 chars)
- [ ] `description` and `text` max_length enforced (e.g., 10000 chars)
- [ ] `due_date` validated as YYYY-MM-DD format if provided
- [ ] FastAPI returns 422 with clear message for validation failures

## Work Log
- 2026-03-20: Identified by security-sentinel and architecture-strategist agents
