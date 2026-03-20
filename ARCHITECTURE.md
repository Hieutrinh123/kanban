# Kanban Board — Architecture

## Overview

A local-first Kanban board that runs entirely on your machine. The frontend is a
single HTML file served by a Python backend. All data lives in a SQLite database.
Claude AI is embedded as a collaborator — mention `@claude` in any comment or
reply and it will respond in-thread.

---

## Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Frontend   | Vanilla HTML/CSS/JS               |
| Fonts      | DM Sans, Syne (Google Fonts)      |
| Markdown   | marked.js (CDN)                   |
| Backend    | Python 3.12 + FastAPI             |
| Server     | Uvicorn (ASGI)                    |
| Database   | SQLite (`kanban.db`) via sqlite3  |
| AI         | Claude CLI (`claude -p`)          |

---

## Project Structure

```
kanban/
├── main.py          — FastAPI app, all REST routes, Claude integration
├── database.py      — SQLite connection, schema init
├── kanban.db        — SQLite database (single source of truth)
├── static/
│   ├── index.html   — HTML shell
│   ├── app.js       — Frontend SPA (Vanilla JS)
│   └── style.css    — Styles
├── requirements.txt
├── start.bat        — Windows launcher
├── start.sh         — Unix launcher
└── ARCHITECTURE.md  — This file
```

---

## Database Schema

```
columns
  id INTEGER PK
  name TEXT              — "Backlog" | "To Do" | "In Progress" | "Done"
  position INTEGER

cards
  id INTEGER PK
  title TEXT
  description TEXT       — maps to "notes" in the frontend
  column_id INTEGER → columns.id
  position INTEGER
  due_date TEXT          — YYYY-MM-DD
  priority TEXT          — "none" | "low" | "medium" | "high"
  project TEXT
  assignee TEXT
  archived INTEGER       — 0 | 1
  created_at TEXT
  updated_at TEXT

checklists
  id INTEGER PK
  card_id INTEGER → cards.id  (CASCADE DELETE)
  title TEXT
  position INTEGER

checklist_items          — maps to "subtasks" in the frontend
  id INTEGER PK
  checklist_id INTEGER → checklists.id  (CASCADE DELETE)
  text TEXT
  completed INTEGER      — 0 | 1
  position INTEGER
  assignee TEXT

comments
  id INTEGER PK
  card_id INTEGER → cards.id  (CASCADE DELETE)
  author TEXT            — "hieu" | "claude"
  text TEXT
  has_at_claude INTEGER  — 1 if comment contains @claude
  claude_handled INTEGER — 1 after Claude has replied
  reply_to_id INTEGER → comments.id  (SET NULL on delete)
  created_at TEXT

Column ID mapping:  1=backlog  2=todo  3=doing  4=done
```

---

## Features

- **4-column Kanban board** — Backlog, To Do, In Progress, Done
- **Cards** — title, notes, due date, priority, project tag, assignee
- **Subtasks** — checklist items per card with assignee and completion toggle
- **Drag & drop** — reorder cards within and across columns
- **Detail panel** — slides in from right, full card editing
- **Comments** — markdown rendered, newest-first, edit/delete
- **Threaded replies** — Claude replies nested under the triggering comment
- **@claude mentions** — tag Claude in any comment to get an AI reply
- **Archive** — soft-delete cards, restore from archive panel
- **Project tags** — color-coded labels per card
- **Sort** — by priority or due date
- **Sync indicator** — shows server connection status

---

## User Flow

```
1. Open browser → localhost:3000
2. Frontend loads → GET /api/board → renders columns and cards
3. User creates/edits cards via modal — each action calls the REST API directly
4. Responses update local state; board re-fetches after moves/deletes

@claude flow:
1. User types "@claude ..." in a comment and submits
2. POST /api/cards/{id}/comments → backend detects @claude in text
3. Backend spawns `claude -p` subprocess with card context as a background task
4. Claude's reply is written to comments table (reply_to_id = trigger comment id)
5. Frontend polls GET /api/cards/{id}/comments every 2s until reply appears
```

---

## Data Flow

```
Browser
  │
  │  GET /api/board
  │  ←────────────────────────────────────────────────────────
  │  kanban.db → columns + cards with aggregate counts
  │
  │  REST actions (POST/PATCH/DELETE /api/cards, /api/checklists, etc.)
  │  ────────────────────────────────────────────────────────→
  │  targeted upserts to kanban.db, returns updated resource
  │
FastAPI (main.py)
  │
  ├── get_board()         columns with cards + item/comment counts
  ├── get_card_full()     card with checklists + comments
  ├── claude_reply()      background task: build prompt → claude -p subprocess
  │                       → INSERT reply comment (reply_to_id set)
  │                       → UPDATE trigger comment SET claude_handled=1
  │
SQLite (kanban.db)
  └── single source of truth
```

---

## API Reference

### Board

| Method | Path          | Description                   |
|--------|---------------|-------------------------------|
| GET    | `/api/board`  | All columns with cards        |

### Cards

| Method | Path                        | Description                        |
|--------|-----------------------------|------------------------------------|
| POST   | `/api/cards`                | Create card                        |
| GET    | `/api/cards/{id}`           | Get card with checklists + comments|
| PATCH  | `/api/cards/{id}`           | Update fields                      |
| DELETE | `/api/cards/{id}`           | Delete card                        |
| POST   | `/api/cards/{id}/move`      | Move to column / reorder           |
| PATCH  | `/api/cards/{id}/archive`   | Archive or unarchive               |

### Archive

| Method | Path           | Description          |
|--------|----------------|----------------------|
| GET    | `/api/archive` | All archived cards   |

### Checklists

| Method | Path                            | Description       |
|--------|---------------------------------|-------------------|
| POST   | `/api/cards/{id}/checklists`    | Create checklist  |
| PATCH  | `/api/checklists/{id}`          | Rename checklist  |
| DELETE | `/api/checklists/{id}`          | Delete checklist  |

### Checklist Items

| Method | Path                               | Description            |
|--------|------------------------------------|------------------------|
| POST   | `/api/checklists/{id}/items`       | Add item               |
| PATCH  | `/api/checklist-items/{id}`        | Toggle / edit item     |
| DELETE | `/api/checklist-items/{id}`        | Delete item            |

### Comments

| Method | Path                          | Description                          |
|--------|-------------------------------|--------------------------------------|
| GET    | `/api/cards/{id}/comments`    | List all comments (flat)             |
| POST   | `/api/cards/{id}/comments`    | Add comment, triggers Claude if @claude |
| PATCH  | `/api/comments/{id}`          | Edit comment text                    |
| DELETE | `/api/comments/{id}`          | Delete comment                       |

Interactive docs: **http://localhost:3000/docs**

---

## Running Locally

```bash
# Windows
start.bat

# Unix / WSL
./start.sh

# Manual
python -m uvicorn main:app --host 127.0.0.1 --port 3000
```

Requires `claude` CLI to be authenticated for @claude features.
