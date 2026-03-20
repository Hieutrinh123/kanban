---
name: renderMarkdown + innerHTML is one regex mistake from stored XSS
description: Current implementation is safe but the esc()->replace() ordering is fragile; any future regex change could open XSS
type: p3
status: pending
priority: p3
issue_id: "012"
tags: [code-review, security, frontend]
---

## Problem Statement

`renderMarkdown` (`app.js:646-652`) HTML-escapes the text first, then uses `.replace()` to inject raw HTML tags (`<strong>`, `<em>`, `<code>`, `<br>`). The output is set via `innerHTML` at `app.js:634`.

The current implementation is safe because `esc()` runs before any `replace()`. However:
1. The safety depends entirely on call order — a future developer reordering the calls opens stored XSS
2. There is no comment explaining why this ordering is mandatory
3. The `esc()` function doesn't escape single quotes, which is fine for div content but not attribute contexts

Claude-generated text also flows through this path; if prompt injection causes Claude to output crafted markdown, it renders as HTML.

## Proposed Solutions

### Option A: Add warning comment + use DOM API for tags (Recommended)
Replace `innerHTML` with `textContent` for the base text, and build `<strong>`/`<em>`/`<code>` nodes using `document.createElement` + `textContent`. This makes XSS structurally impossible.

### Option B: Add DOMPurify
Include `DOMPurify` (already using CDN for `marked.js`) and sanitize before innerHTML assignment.

### Option C: Document the ordering constraint
At minimum, add a comment: `// IMPORTANT: esc() MUST run before all replace() calls to prevent XSS`

**Effort:** Small (option C) to Medium (option A) | **Risk:** Low

## Acceptance Criteria
- [ ] Either: code uses DOM API making XSS structurally impossible
- [ ] Or: DOMPurify sanitizes before any innerHTML assignment
- [ ] Or: ordering constraint documented and covered by a comment

## Work Log
- 2026-03-20: Identified by security-sentinel agent
