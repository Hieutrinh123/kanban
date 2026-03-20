---
name: Dual frontend causes silent card deletion
description: Old /data POST endpoint deletes cards not in its payload; coexists with new REST API on same static/ dir
type: p1
status: complete
priority: p1
issue_id: "001"
tags: [code-review, architecture, data-integrity]
---

## Problem Statement

Two separate frontend SPA files are served from the same `static/` directory:
- **New:** `static/index.html` + `static/app.js` — uses `/api/*` REST endpoints
- **Old:** Legacy full-board-sync flow — uses `POST /data`

The `_sync_to_db` function (`main.py:136-138`) computes `existing_ids - incoming_ids` and **deletes every card not in the POST body**. If a user opens the old SPA in one browser tab while using the new one in another, the old SPA's next sync will permanently delete all cards created through the new REST API.

## Findings

- `main.py:100-150`: `_sync_to_db` deletes cards missing from POST body
- `main.py:110-113`: `existing_ids` fetches all non-archived card IDs
- `main.py:136-138`: `DELETE FROM cards WHERE id=?` for every ID not in the incoming payload
- ARCHITECTURE.md describes the old system as the active one — misleads developers into reading the wrong code path

## Proposed Solutions

### Option A: Delete the legacy endpoints and dead code (Recommended)
Remove `GET /data`, `POST /data`, `_sync_to_db`, `_sync_subtasks`, `_sync_comments`, `process_pending_claude`, `_ts`, `_dt`, `_try_int`, `COL_ID_TO_KEY`, `COL_KEY_TO_ID` (~180 lines). Update ARCHITECTURE.md to reflect the REST API flow.

**Pros:** Eliminates the data-loss hazard, simplifies codebase significantly, removes ~180 lines of dead code
**Cons:** Irreversible if the old UI is still needed (it appears it is not)
**Effort:** Medium | **Risk:** Low (frontend uses only `/api/*`)

### Option B: Protect the /data endpoint with a flag
Add a config flag that disables `POST /data` by default, so accidental access cannot trigger deletions.

**Pros:** Preserves old code as reference
**Cons:** Still confusing, does not fix ARCHITECTURE.md, two Claude integration paths remain
**Effort:** Small | **Risk:** Medium

## Acceptance Criteria
- [ ] `POST /data` and `GET /data` endpoints removed or safely gated
- [ ] No path exists to silently delete cards via old sync logic
- [ ] ARCHITECTURE.md updated to describe only the live REST API flow
- [ ] `process_pending_claude` and supporting legacy functions removed

## Work Log
- 2026-03-20: Identified by architecture-strategist review agent
