---
name: Comment author field allows spoofing Claude identity
description: POST /api/cards/{id}/comments accepts any author string, enabling fake Claude comments that are undeletable via the UI
type: p2
status: pending
priority: p2
issue_id: "004"
tags: [code-review, security, quality]
---

## Problem Statement

`CommentCreate` model (`main.py:308-310`) accepts `author: str = "user"` from the request body with no validation. A caller can POST `{"text": "hello", "author": "claude"}` and create a comment stored with `author = "claude"`.

Consequences:
1. Frontend renders fake-Claude comments with the robot avatar and hides Edit/Delete buttons (`app.js:617-624`)
2. The comment becomes **undeletable** through the normal UI
3. `_sync_comments` excludes claude-authored comments from deletion (`main.py:168-195`)

## Findings

- `main.py:308-310`: `class CommentCreate(BaseModel): author: str = "user"`
- `main.py:606-609`: `author` passed directly to INSERT without validation
- `app.js:617-624`: `const isClaude = c.author === 'claude'` — controls avatar and action buttons
- `main.py:168`: `existing = {r[0] for r in conn.execute("SELECT id FROM comments WHERE card_id=? AND reply_to_id IS NULL", ...)}` — does not exclude claude comments from the deletion candidate set, but the frontend won't show delete for them

## Proposed Solutions

### Option A: Remove author from CommentCreate entirely (Recommended)
Backend always writes `author = "user"` for user-created comments. Only `claude_reply` writes `author = "claude"`.

```python
class CommentCreate(BaseModel):
    text: str
    # author field removed — backend always assigns "user"

# In create_comment:
cur = conn.execute(
    "INSERT INTO comments (card_id, author, text, has_at_claude) VALUES (?,?,?,?)",
    (card_id, "user", body.text, has_at_claude),
)
```

**Pros:** Eliminates spoofing entirely, simplest fix
**Effort:** Small | **Risk:** Low

### Option B: Validate author against allowed values
Reject any value other than "user" from the client, raise HTTP 422.

**Pros:** Preserves field in case multiple human authors are ever needed
**Effort:** Small | **Risk:** Low

## Acceptance Criteria
- [ ] Client cannot create a comment with `author = "claude"`
- [ ] All user-created comments stored with `author = "user"` regardless of request body
- [ ] Existing fake-Claude comments can be deleted via admin endpoint if needed

## Work Log
- 2026-03-20: Identified by security-sentinel agent
