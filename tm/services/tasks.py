"""Task service."""

from __future__ import annotations

import sqlite3
import uuid

from tm.dates import fmt_time, now_iso, parse_time_min
from tm.errors import bad_request, not_found
from tm.models import TaskCreate, TaskUpdate

TASK_SELECT = "SELECT * FROM tasks"


def _row_to_task(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "project": row["project"],
        "notes": row["notes"],
        "deadline": row["deadline_date"],
        "deadline_time": (
            fmt_time(row["deadline_min"]) if row["deadline_min"] is not None else None
        ),
        "done": bool(row["done"]),
        "done_at": row["done_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_row(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
    row = conn.execute(f"{TASK_SELECT} WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise not_found("task", task_id)
    return row


def get_task(conn: sqlite3.Connection, task_id: str) -> dict:
    return _row_to_task(_get_row(conn, task_id))


def list_tasks(
    conn: sqlite3.Connection,
    *,
    status: str = "all",
    project: str | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if status == "open":
        clauses.append("done = 0")
    elif status == "done":
        clauses.append("done = 1")
    elif status != "all":
        raise bad_request("status must be one of: all, open, done")
    if project is not None:
        clauses.append("project = ?")
        params.append(project)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        {TASK_SELECT}{where}
        ORDER BY CASE WHEN deadline_date IS NULL THEN 1 ELSE 0 END,
                 deadline_date,
                 COALESCE(deadline_min, 1439),
                 created_at
        """,
        params,
    ).fetchall()
    return [_row_to_task(row) for row in rows]


def create_task(conn: sqlite3.Connection, data: TaskCreate) -> dict:
    now = now_iso()
    task_id = str(uuid.uuid4())
    deadline_min = (
        parse_time_min(data.deadline_time) if data.deadline_time is not None else None
    )
    with conn:
        conn.execute(
            """
            INSERT INTO tasks
              (id, title, project, notes, deadline_date, deadline_min, done,
               done_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
            """,
            (
                task_id,
                data.title,
                data.project or None,
                data.notes,
                data.deadline,
                deadline_min,
                now,
                now,
            ),
        )
    return get_task(conn, task_id)


def update_task(conn: sqlite3.Connection, task_id: str, data: TaskUpdate) -> dict:
    row = _get_row(conn, task_id)
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return _row_to_task(row)

    if "title" in fields and fields["title"] is None:
        raise bad_request("title must not be null")
    if "done" in fields and fields["done"] is None:
        raise bad_request("done must be true or false")

    deadline = fields.get("deadline", row["deadline_date"])
    if "deadline_time" in fields:
        deadline_time = fields["deadline_time"]
    elif "deadline" in fields and fields["deadline"] is None:
        deadline_time = None
    else:
        deadline_time = (
            fmt_time(row["deadline_min"]) if row["deadline_min"] is not None else None
        )

    if deadline is None and deadline_time is not None:
        raise bad_request("deadline_time requires a deadline date")

    done = fields.get("done", bool(row["done"]))
    done_at = row["done_at"]
    if done and not row["done"]:
        done_at = now_iso()
    elif not done:
        done_at = None

    with conn:
        conn.execute(
            """
            UPDATE tasks
               SET title = ?, project = ?, notes = ?, deadline_date = ?,
                   deadline_min = ?, done = ?, done_at = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                fields.get("title", row["title"]),
                fields.get("project", row["project"]) or None,
                fields.get("notes", row["notes"]) or "",
                deadline,
                parse_time_min(deadline_time) if deadline_time is not None else None,
                int(done),
                done_at,
                now_iso(),
                task_id,
            ),
        )
    return get_task(conn, task_id)


def set_done(conn: sqlite3.Connection, task_id: str, done: bool = True) -> dict:
    return update_task(conn, task_id, TaskUpdate(done=done))


def delete_task(conn: sqlite3.Connection, task_id: str) -> None:
    _get_row(conn, task_id)
    with conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
