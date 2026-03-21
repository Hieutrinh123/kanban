import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "kanban.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS columns (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            position INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS cards (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            description TEXT    NOT NULL DEFAULT '',
            column_id   INTEGER NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
            position    INTEGER NOT NULL DEFAULT 0,
            due_date    TEXT,
            priority    TEXT    NOT NULL DEFAULT 'none',
            project     TEXT,
            assignee    TEXT,
            archived    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS checklists (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id  INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            title    TEXT    NOT NULL DEFAULT 'Checklist',
            position INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS checklist_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_id INTEGER NOT NULL REFERENCES checklists(id) ON DELETE CASCADE,
            text         TEXT    NOT NULL,
            completed    INTEGER NOT NULL DEFAULT 0,
            position     INTEGER NOT NULL DEFAULT 0,
            assignee     TEXT
        );

        CREATE TABLE IF NOT EXISTS comments (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id        INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            author         TEXT    NOT NULL DEFAULT 'user',
            text           TEXT    NOT NULL DEFAULT '',
            has_at_claude  INTEGER NOT NULL DEFAULT 0,
            claude_handled INTEGER NOT NULL DEFAULT 0,
            reply_to_id    INTEGER REFERENCES comments(id) ON DELETE SET NULL,
            status         TEXT    NOT NULL DEFAULT 'done',
            created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)

    # Add new columns to existing tables if upgrading from older schema
    for sql in [
        "ALTER TABLE cards ADD COLUMN project TEXT",
        "ALTER TABLE cards ADD COLUMN assignee TEXT",
        "ALTER TABLE checklist_items ADD COLUMN assignee TEXT",
        "ALTER TABLE comments ADD COLUMN has_at_claude INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE comments ADD COLUMN claude_handled INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE comments ADD COLUMN reply_to_id INTEGER REFERENCES comments(id) ON DELETE SET NULL",
        "ALTER TABLE comments ADD COLUMN status TEXT NOT NULL DEFAULT 'done'",
        "ALTER TABLE cards ADD COLUMN file_path TEXT",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass  # column already exists

    count = conn.execute("SELECT COUNT(*) FROM columns").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO columns (name, position) VALUES (?, ?)",
            [("Backlog", 0), ("To Do", 1), ("In Progress", 2), ("Done", 3)],
        )
    conn.commit()
    conn.close()
