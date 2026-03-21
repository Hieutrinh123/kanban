from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_PATH = Path(__file__).parent / "server.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("kanban")

import database

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

app = FastAPI(title="Kanban Board")
database.init_db()


@app.get("/api/browse")
async def browse_file():
    """Show a File / Folder choice popup then open the appropriate native picker."""
    if sys.platform == "win32":
        # Tkinter cannot be used from a thread executor on Windows.
        # Use a PowerShell WinForms form for the whole flow.
        # One dialog for both files and folders.
        # A TopMost invisible owner form forces the dialog in front of the browser.
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$owner=New-Object System.Windows.Forms.Form;"
            "$owner.TopMost=$true;"
            "$owner.WindowState='Minimized';"
            "$owner.ShowInTaskbar=$false;"
            "$owner.Show();"
            "$d=New-Object System.Windows.Forms.OpenFileDialog;"
            "$d.Title='Select a file or folder';"
            "$d.ValidateNames=$false;"
            "$d.CheckFileExists=$false;"
            "$d.CheckPathExists=$false;"
            "$d.FileName='Select Folder.';"
            "if($d.ShowDialog($owner)-eq'OK'){"
            "  $p=$d.FileName;"
            "  if([System.IO.File]::Exists($p)){$p}"
            "  elseif([System.IO.Directory]::Exists($p)){$p}"
            "  else{Split-Path $p}"
            "}else{''};"
            "$owner.Dispose();"
        )

        def _run():
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=60,
            )
            return r.stdout.strip() or None

        loop = asyncio.get_running_loop()
        selected_path = await loop.run_in_executor(None, _run)
    else:
        if not tk:
            raise HTTPException(500, "Tkinter not installed/available")

        def _run():
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(title="Select File or Folder")
            root.destroy()
            return path or None

        loop = asyncio.get_running_loop()
        selected_path = await loop.run_in_executor(None, _run)

    return {"path": selected_path}


# ── Pydantic models ───────────────────────────────────────────────────────────

class CardCreate(BaseModel):
    title: str
    column_id: int
    description: str = ""
    due_date: Optional[str] = None
    priority: str = "none"
    project: Optional[str] = None
    assignee: Optional[str] = None
    file_path: Optional[str] = None


class CardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    project: Optional[str] = None
    assignee: Optional[str] = None
    file_path: Optional[str] = None


class CardMove(BaseModel):
    column_id: int
    source_column_id: int
    source_ids: List[int]
    target_ids: List[int]


class CardArchive(BaseModel):
    archived: bool


class ChecklistCreate(BaseModel):
    title: str = "Checklist"


class ChecklistItemCreate(BaseModel):
    text: str
    assignee: Optional[str] = None


class ChecklistItemUpdate(BaseModel):
    text: Optional[str] = None
    completed: Optional[bool] = None
    assignee: Optional[str] = None


class CommentCreate(BaseModel):
    text: str
    reply_to_id: Optional[int] = None
    author: str = "user"


class CommentUpdate(BaseModel):
    text: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_card_full(conn, card_id: int):
    card = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    if not card:
        return None
    card = dict(card)
    checklists = conn.execute(
        "SELECT * FROM checklists WHERE card_id=? ORDER BY position", (card_id,)
    ).fetchall()
    card["checklists"] = []
    for cl in checklists:
        cl = dict(cl)
        items = conn.execute(
            "SELECT * FROM checklist_items WHERE checklist_id=? ORDER BY position",
            (cl["id"],),
        ).fetchall()
        cl["items"] = [dict(i) for i in items]
        card["checklists"].append(cl)
    comments = conn.execute(
        "SELECT * FROM comments WHERE card_id=? ORDER BY created_at, id",
        (card_id,),
    ).fetchall()
    card["comments"] = [dict(c) for c in comments]
    return card


# ── Board ─────────────────────────────────────────────────────────────────────

@app.get("/api/board")
def get_board():
    conn = database.get_db()
    try:
        columns = conn.execute("SELECT * FROM columns ORDER BY position").fetchall()
        result = []
        for col in columns:
            col = dict(col)
            cards = conn.execute(
                """
                SELECT c.*,
                    (SELECT COUNT(*) FROM checklist_items ci
                     JOIN checklists cl ON ci.checklist_id = cl.id
                     WHERE cl.card_id = c.id) AS total_items,
                    (SELECT COUNT(*) FROM checklist_items ci
                     JOIN checklists cl ON ci.checklist_id = cl.id
                     WHERE cl.card_id = c.id AND ci.completed = 1) AS completed_items,
                    (SELECT COUNT(*) FROM comments cm WHERE cm.card_id = c.id) AS comment_count
                FROM cards c
                WHERE c.column_id = ? AND c.archived = 0
                ORDER BY c.position
                """,
                (col["id"],),
            ).fetchall()
            col["cards"] = [dict(c) for c in cards]
            result.append(col)
        return result
    finally:
        conn.close()


# ── Cards ─────────────────────────────────────────────────────────────────────

@app.post("/api/cards", status_code=201)
def create_card(body: CardCreate):
    conn = database.get_db()
    try:
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM cards WHERE column_id=? AND archived=0",
            (body.column_id,),
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO cards (title, description, column_id, position, due_date, priority, project, assignee, file_path) VALUES (?,?,?,?,?,?,?,?,?)",
            (body.title, body.description, body.column_id, max_pos + 1, body.due_date, body.priority, body.project, body.assignee, body.file_path),
        )
        conn.commit()
        return get_card_full(conn, cur.lastrowid)
    finally:
        conn.close()


@app.get("/api/cards/{card_id}")
def get_card(card_id: int):
    conn = database.get_db()
    try:
        card = get_card_full(conn, card_id)
        if not card:
            raise HTTPException(404, "Card not found")
        return card
    finally:
        conn.close()


@app.patch("/api/cards/{card_id}")
def update_card(card_id: int, body: CardUpdate):
    conn = database.get_db()
    try:
        card = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not card:
            raise HTTPException(404, "Card not found")
        updates = {k: v for k, v in body.model_dump().items() if k in body.model_fields_set}
        if not updates:
            return get_card_full(conn, card_id)
        set_parts = [f"{k}=?" for k in updates]
        set_parts.append("updated_at=datetime('now')")
        values = list(updates.values()) + [card_id]
        conn.execute(f"UPDATE cards SET {', '.join(set_parts)} WHERE id=?", values)
        conn.commit()
        return get_card_full(conn, card_id)
    finally:
        conn.close()


@app.delete("/api/cards/{card_id}", status_code=204)
def delete_card(card_id: int):
    conn = database.get_db()
    try:
        conn.execute("DELETE FROM cards WHERE id=?", (card_id,))
        conn.commit()
    finally:
        conn.close()


@app.post("/api/cards/{card_id}/move")
def move_card(card_id: int, body: CardMove):
    conn = database.get_db()
    try:
        # Verify card exists
        card = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not card:
            raise HTTPException(404, "Card not found")
            
        # Update source column positions
        for pos, cid in enumerate(body.source_ids):
            conn.execute("UPDATE cards SET position=? WHERE id=?", (pos, cid))
            
        # Update target column positions and move the card
        for pos, cid in enumerate(body.target_ids):
            conn.execute(
                "UPDATE cards SET column_id=?, position=?, updated_at=datetime('now') WHERE id=?",
                (body.column_id, pos, cid),
            )
        
        # Ensure the specific card_id is in the target column at some position
        # (The frontend usually includes it in target_ids, but we'll be explicit)
        conn.execute(
            "UPDATE cards SET column_id=?, updated_at=datetime('now') WHERE id=?",
            (body.column_id, card_id),
        )
        
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.patch("/api/cards/{card_id}/archive")
def archive_card(card_id: int, body: CardArchive):
    conn = database.get_db()
    try:
        conn.execute(
            "UPDATE cards SET archived=?, updated_at=datetime('now') WHERE id=?",
            (1 if body.archived else 0, card_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── Archive ───────────────────────────────────────────────────────────────────

@app.get("/api/archive")
def get_archive():
    conn = database.get_db()
    try:
        cards = conn.execute(
            """
            SELECT c.*, col.name AS column_name
            FROM cards c
            JOIN columns col ON c.column_id = col.id
            WHERE c.archived = 1
            ORDER BY c.updated_at DESC
            """
        ).fetchall()
        return [dict(c) for c in cards]
    finally:
        conn.close()


# ── Checklists ────────────────────────────────────────────────────────────────

@app.post("/api/cards/{card_id}/checklists", status_code=201)
def create_checklist(card_id: int, body: ChecklistCreate):
    conn = database.get_db()
    try:
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM checklists WHERE card_id=?", (card_id,)
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO checklists (card_id, title, position) VALUES (?,?,?)",
            (card_id, body.title, max_pos + 1),
        )
        conn.commit()
        cl = dict(conn.execute("SELECT * FROM checklists WHERE id=?", (cur.lastrowid,)).fetchone())
        cl["items"] = []
        return cl
    finally:
        conn.close()


@app.patch("/api/checklists/{checklist_id}")
def update_checklist(checklist_id: int, body: ChecklistCreate):
    conn = database.get_db()
    try:
        conn.execute("UPDATE checklists SET title=? WHERE id=?", (body.title, checklist_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM checklists WHERE id=?", (checklist_id,)).fetchone())
    finally:
        conn.close()


@app.delete("/api/checklists/{checklist_id}", status_code=204)
def delete_checklist(checklist_id: int):
    conn = database.get_db()
    try:
        conn.execute("DELETE FROM checklists WHERE id=?", (checklist_id,))
        conn.commit()
    finally:
        conn.close()


# ── Checklist items ───────────────────────────────────────────────────────────

@app.post("/api/checklists/{checklist_id}/items", status_code=201)
def create_checklist_item(checklist_id: int, body: ChecklistItemCreate):
    conn = database.get_db()
    try:
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM checklist_items WHERE checklist_id=?",
            (checklist_id,),
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO checklist_items (checklist_id, text, position, assignee) VALUES (?,?,?,?)",
            (checklist_id, body.text, max_pos + 1, body.assignee),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM checklist_items WHERE id=?", (cur.lastrowid,)).fetchone())
    finally:
        conn.close()


@app.patch("/api/checklist-items/{item_id}")
def update_checklist_item(item_id: int, body: ChecklistItemUpdate):
    conn = database.get_db()
    try:
        item = conn.execute("SELECT * FROM checklist_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise HTTPException(404, "Item not found")
        updates = {k: v for k, v in body.model_dump().items() if k in body.model_fields_set}
        if "completed" in updates:
            updates["completed"] = 1 if updates["completed"] else 0
        if not updates:
            return dict(item)
        set_parts = [f"{k}=?" for k in updates]
        values = list(updates.values()) + [item_id]
        conn.execute(f"UPDATE checklist_items SET {', '.join(set_parts)} WHERE id=?", values)
        conn.commit()
        return dict(conn.execute("SELECT * FROM checklist_items WHERE id=?", (item_id,)).fetchone())
    finally:
        conn.close()


@app.delete("/api/checklist-items/{item_id}", status_code=204)
def delete_checklist_item(item_id: int):
    conn = database.get_db()
    try:
        conn.execute("DELETE FROM checklist_items WHERE id=?", (item_id,))
        conn.commit()
    finally:
        conn.close()


# ── Comments ──────────────────────────────────────────────────────────────────

@app.get("/api/cards/{card_id}/comments")
def get_comments(card_id: int):
    conn = database.get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM comments WHERE card_id=? ORDER BY created_at, id",
            (card_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.post("/api/cards/{card_id}/comments", status_code=201)
def create_comment(card_id: int, body: CommentCreate):
    conn = database.get_db()
    try:
        card = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not card:
            raise HTTPException(404, "Card not found")
        has_at_claude = 1 if "@claude" in body.text.lower() else 0
        cur = conn.execute(
            "INSERT INTO comments (card_id, author, text, has_at_claude, reply_to_id) VALUES (?,?,?,?,?)",
            (card_id, "user", body.text, has_at_claude, body.reply_to_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM comments WHERE id=?", (cur.lastrowid,)).fetchone())
    finally:
        conn.close()


@app.patch("/api/comments/{comment_id}")
def update_comment(comment_id: int, body: CommentUpdate):
    conn = database.get_db()
    try:
        comment = conn.execute("SELECT * FROM comments WHERE id=?", (comment_id,)).fetchone()
        if not comment:
            raise HTTPException(404, "Comment not found")
        conn.execute("UPDATE comments SET text=? WHERE id=?", (body.text, comment_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM comments WHERE id=?", (comment_id,)).fetchone())
    finally:
        conn.close()


@app.delete("/api/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: int):
    conn = database.get_db()
    try:
        conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
        conn.commit()
    finally:
        conn.close()


# ── Claude reply background task ──────────────────────────────────────────────

def _build_claude_prompt(card: dict, comment_text: str, parent_text: str = None) -> str:
    lines = [
        "You are an AI assistant embedded in a Kanban board. Respond concisely and helpfully.",
        "",
        "## Task",
        f"**Title:** {card['title']}",
    ]
    if card.get("description"):
        lines.append(f"**Description:** {card['description']}")
    if card.get("priority") and card["priority"] != "none":
        lines.append(f"**Priority:** {card['priority']}")
    if card.get("due_date"):
        lines.append(f"**Due:** {card['due_date']}")


    # Fetch and include checklist items
    conn = database.get_db()
    try:
        checklists = conn.execute(
            "SELECT * FROM checklists WHERE card_id=? ORDER BY position", (card["id"],)
        ).fetchall()
        for cl in checklists:
            items = conn.execute(
                "SELECT * FROM checklist_items WHERE checklist_id=? ORDER BY position", (cl["id"],)
            ).fetchall()
            if items:
                lines.append(f"\n**{cl['title']}:**")
                for item in items:
                    mark = "x" if item["completed"] else " "
                    lines.append(f"- [{mark}] {item['text']}")
    finally:
        conn.close()

    # Include referenced file content if path is provided
    if card.get("file_path"):
        fpath = Path(card["file_path"])
        if fpath.exists() and fpath.is_file():
            try:
                # Basic safety: skip files > 100KB or binary-ish
                if fpath.stat().st_size < 100_000:
                    content = fpath.read_text(errors="replace")
                    lines.append(f"\n## Referenced File: {fpath.name}")
                    lines.append("```")
                    lines.append(content)
                    lines.append("```")
                else:
                    lines.append(f"\n## Referenced File: {fpath.name}")
                    lines.append("(File is too large to include full content)")
            except Exception as e:
                lines.append(f"\n## Referenced File Error")
                lines.append(f"Could not read {fpath.name}: {str(e)}")

    if parent_text:
        lines += ["", "## Discussion Context (Previous Comment)", parent_text]

    lines += [
        "",
        "## Current Comment",
        comment_text,
        "",
        "## Instruction",
        "Reply to the comment above. The user tagged @claude to ask for your help.",
    ]
    return "\n".join(lines)


def _claude_cmd() -> tuple[list[str], bool]:
    """Return the command list to invoke the claude CLI and a boolean if found."""
    for name in ("claude", "claude.cmd", "claude.exe"):
        path = shutil.which(name)
        if path:
            if sys.platform == "win32" and path.lower().endswith(".cmd"):
                # Use full path to cmd.exe — bare "cmd" can fail in CreateProcess
                # when the server is started without a full system PATH.
                cmd_exe = shutil.which("cmd") or r"C:\Windows\System32\cmd.exe"
                return [cmd_exe, "/c", path, "-p"], True
            return [path, "-p"], True

    return ["claude", "-p"], False


async def claude_reply(card_id: int, card: dict, comment_text: str, trigger_comment_id: int):
    cmd, found = _claude_cmd()
    if not found:
        reply_text = (
            "⚠️ Error: Claude CLI was not found on your system PATH.\n\n"
            "To fix this:\n"
            "1. Install the Claude CLI (`npm install -g @anthropic-ai/claude-code`)\n"
            "2. Ensure it is in your Windows Environment PATH.\n"
            "3. Or, if you use a different name/path, update `_claude_cmd` in `main.py`."
        )
    else:
        # Fetch parent context if this is a reply
        conn = database.get_db()
        parent_text = None
        try:
            trigger_cmt = conn.execute("SELECT reply_to_id FROM comments WHERE id=?", (trigger_comment_id,)).fetchone()
            if trigger_cmt and trigger_cmt["reply_to_id"]:
                parent = conn.execute("SELECT text FROM comments WHERE id=?", (trigger_cmt["reply_to_id"],)).fetchone()
                if parent:
                    parent_text = parent["text"]
        finally:
            conn.close()

        prompt = _build_claude_prompt(card, comment_text, parent_text)
        try:
            # Use subprocess.run in a thread — more reliable than
            # asyncio.create_subprocess_exec on Windows for .cmd wrappers.
            loop = asyncio.get_running_loop()
            def _run():
                result = subprocess.run(
                    cmd,
                    input=prompt.encode("utf-8"),
                    capture_output=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    return result.stdout.decode("utf-8").strip()
                return f"⚠️ {result.stderr.decode('utf-8').strip()}"
            reply_text = await loop.run_in_executor(None, _run)
        except subprocess.TimeoutExpired:
            reply_text = "⚠️ Request timed out after 120 seconds. Claude CLI might be hanging or your internet is very slow."
        except Exception as e:
            reply_text = f"⚠️ Error running Claude CLI: {str(e)}"

    conn = database.get_db()
    try:
        conn.execute(
            "INSERT INTO comments (card_id, author, text, reply_to_id) VALUES (?,?,?,?)",
            (card_id, "claude", reply_text, trigger_comment_id),
        )
        conn.execute(
            "UPDATE comments SET claude_handled=1 WHERE id=?",
            (trigger_comment_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ── Claude streaming endpoint ─────────────────────────────────────────────────

@app.get("/api/claude-stream/{comment_id}")
async def claude_stream(comment_id: int):
    """Stream Claude's reply token-by-token as SSE, then persist to DB."""
    conn = database.get_db()
    try:
        cmt = conn.execute("SELECT * FROM comments WHERE id=?", (comment_id,)).fetchone()
        if not cmt:
            raise HTTPException(404, "Comment not found")
        cmt = dict(cmt)
        card = conn.execute("SELECT * FROM cards WHERE id=?", (cmt["card_id"],)).fetchone()
        if not card:
            raise HTTPException(404, "Card not found")
        card = dict(card)
    finally:
        conn.close()

    def _sse(text: str) -> str:
        """JSON-encode chunk so newlines are never stripped by SSE parser."""
        import json
        return f"data: {json.dumps(text)}\n\n"

    async def generate():
        try:
            cmd, found = _claude_cmd()
            log.info(f"[stream:{comment_id}] Starting — claude found={found}, cmd={cmd}")

            if not found:
                error_text = (
                    "⚠️ Claude CLI not found on PATH.\n\n"
                    "Fix: npm install -g @anthropic-ai/claude-code, then restart the server."
                )
                log.error(f"[stream:{comment_id}] Claude CLI not found")
                yield _sse(error_text)
                _persist(cmt["card_id"], comment_id, error_text)
                yield "data: [DONE]\n\n"
                return

            # Fetch parent context
            parent_text = None
            if cmt.get("reply_to_id"):
                conn2 = database.get_db()
                try:
                    parent = conn2.execute(
                        "SELECT text FROM comments WHERE id=?", (cmt["reply_to_id"],)
                    ).fetchone()
                    if parent:
                        parent_text = parent["text"]
                finally:
                    conn2.close()

            prompt = _build_claude_prompt(card, cmt["text"], parent_text)
            log.info(f"[stream:{comment_id}] Prompt built ({len(prompt)} chars), launching Claude")

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue()

            def _producer():
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    proc.stdin.write(prompt.encode("utf-8"))
                    proc.stdin.close()
                    byte_count = 0
                    while True:
                        chunk = proc.stdout.read(64)
                        if not chunk:
                            break
                        byte_count += len(chunk)
                        loop.call_soon_threadsafe(
                            queue.put_nowait, chunk.decode("utf-8", errors="replace")
                        )
                    proc.wait()
                    log.info(f"[stream:{comment_id}] Claude exited code={proc.returncode}, bytes={byte_count}")
                    if proc.returncode != 0:
                        err = proc.stderr.read().decode("utf-8", errors="replace").strip()
                        log.error(f"[stream:{comment_id}] Claude stderr: {err}")
                        if err:
                            loop.call_soon_threadsafe(queue.put_nowait, f"\n\n⚠️ Claude error: {err}")
                except Exception as exc:
                    tb = traceback.format_exc()
                    log.error(f"[stream:{comment_id}] Producer exception: {tb}")
                    loop.call_soon_threadsafe(queue.put_nowait, f"\n\n⚠️ Server error: {exc}")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            threading.Thread(target=_producer, daemon=True).start()

            full_parts: list[str] = []
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                full_parts.append(chunk)
                yield _sse(chunk)

            full_reply = "".join(full_parts)
            log.info(f"[stream:{comment_id}] Done — {len(full_reply)} chars, persisting to DB")
            _persist(cmt["card_id"], comment_id, full_reply)
            yield "data: [DONE]\n\n"

        except Exception as exc:
            tb = traceback.format_exc()
            log.error(f"[stream:{comment_id}] Unhandled exception in generate():\n{tb}")
            try:
                yield _sse(f"⚠️ Server error: {exc}")
                yield "data: [DONE]\n\n"
            except Exception:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _persist(card_id: int, trigger_comment_id: int, reply_text: str):
    conn = database.get_db()
    try:
        conn.execute(
            "INSERT INTO comments (card_id, author, text, reply_to_id) VALUES (?,?,?,?)",
            (card_id, "claude", reply_text, trigger_comment_id),
        )
        conn.execute(
            "UPDATE comments SET claude_handled=1 WHERE id=?", (trigger_comment_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ── Static files (must be last) ───────────────────────────────────────────────

app.mount("/", StaticFiles(directory="static", html=True), name="static")
