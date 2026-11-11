"""Blocks: appointments and scheduled work sessions."""

from __future__ import annotations

import sqlite3
import uuid

from tm.dates import (
    ceil_to_grid,
    fmt_time,
    now_iso,
    now_minutes,
    parse_date,
    parse_time_min,
    today,
)
from tm.errors import AppError, bad_request, not_found
from tm.models import BlockCreate, BlockUpdate, SessionCreate
from tm.services.settings import get_settings
from tm.services.tasks import get_task

BLOCK_SELECT = """
SELECT b.*, t.title AS task_title, t.project AS task_project, t.done AS task_done
FROM blocks b
LEFT JOIN tasks t ON t.id = b.task_id
"""


def _row_to_block(row: sqlite3.Row) -> dict:
    all_day = row["start_min"] is None
    return {
        "id": row["id"],
        "title": row["title"],
        "kind": row["kind"],
        "task_id": row["task_id"],
        "task_title": row["task_title"] if "task_title" in row.keys() else None,
        "task_project": row["task_project"] if "task_project" in row.keys() else None,
        "date": row["date"],
        "start": fmt_time(row["start_min"]) if row["start_min"] is not None else None,
        "end": fmt_time(row["end_min"]) if row["end_min"] is not None else None,
        "all_day": all_day,
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_row(conn: sqlite3.Connection, block_id: str) -> sqlite3.Row:
    row = conn.execute(f"{BLOCK_SELECT} WHERE b.id = ?", (block_id,)).fetchone()
    if row is None:
        raise not_found("block", block_id)
    return row


def get_block(conn: sqlite3.Connection, block_id: str) -> dict:
    return _row_to_block(_get_row(conn, block_id))


def list_blocks(conn: sqlite3.Connection, from_date: str, to_date: str) -> list[dict]:
    rows = conn.execute(
        f"""
        {BLOCK_SELECT}
        WHERE b.date BETWEEN ? AND ?
        ORDER BY b.date, COALESCE(b.start_min, -1), b.created_at
        """,
        (from_date, to_date),
    ).fetchall()
    return [_row_to_block(row) for row in rows]


def _span(start_min: int | None, end_min: int | None) -> tuple[int, int]:
    if start_min is None or end_min is None:
        return 0, 1440
    return start_min, end_min


def _validate_block_time(
    conn: sqlite3.Connection,
    date: str,
    start_min: int | None,
    end_min: int | None,
) -> None:
    """Reject timed blocks that are in the past or outside the schedulable window.

    All-day blocks are day-level markers: they may be added for today even though part
    of the day has passed, but never for a past date.
    """
    settings = get_settings(conn)
    block_date = parse_date(date)
    today_date = today()
    if block_date < today_date:
        raise bad_request("Cannot schedule an appointment or session on a past date.")

    if start_min is None and end_min is None:
        return

    window_start = parse_time_min(settings.day_start)
    window_end = parse_time_min(settings.day_end, allow_end_of_day=True)
    if start_min < window_start or end_min > window_end:
        raise bad_request(
            "Appointments and sessions must be scheduled between "
            f"{settings.day_start} and {settings.day_end}."
        )

    if block_date == today_date:
        earliest = max(
            window_start,
            ceil_to_grid(now_minutes(), settings.granularity_min),
        )
        if start_min < earliest:
            raise bad_request(
                "That time has already passed. "
                f"The next schedulable start is {fmt_time(earliest)}."
            )


def find_conflicts(
    conn: sqlite3.Connection,
    date: str,
    start_min: int | None,
    end_min: int | None,
    *,
    exclude_block_id: str | None = None,
    ignore_done_sessions: bool = True,
) -> list[dict]:
    new_start, new_end = _span(start_min, end_min)
    rows = conn.execute(
        f"{BLOCK_SELECT} WHERE b.date = ? ORDER BY COALESCE(b.start_min, -1)",
        (date,),
    ).fetchall()

    conflicts: list[dict] = []
    for row in rows:
        if exclude_block_id and row["id"] == exclude_block_id:
            continue
        if ignore_done_sessions and row["task_id"] and row["task_done"]:
            continue
        existing_start, existing_end = _span(row["start_min"], row["end_min"])
        if new_start < existing_end and new_end > existing_start:
            conflicts.append(_row_to_block(row))
    return conflicts


def _insert_block(
    conn: sqlite3.Connection,
    *,
    title: str,
    kind: str,
    task_id: str | None,
    date: str,
    start_min: int | None,
    end_min: int | None,
    notes: str,
    allow_overlap: bool,
) -> dict:
    _validate_block_time(conn, date, start_min, end_min)

    conflicts = find_conflicts(conn, date, start_min, end_min)
    if conflicts and not allow_overlap:
        raise AppError(
            409,
            "conflict",
            "This slot overlaps existing blocks. Choose another slot or pass allow_overlap.",
            conflicts,
        )

    block_id = str(uuid.uuid4())
    now = now_iso()
    with conn:
        conn.execute(
            """
            INSERT INTO blocks
              (id, title, kind, task_id, date, start_min, end_min, notes,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block_id,
                title,
                kind,
                task_id,
                date,
                start_min,
                end_min,
                notes,
                now,
                now,
            ),
        )
    return get_block(conn, block_id)


def create_block(conn: sqlite3.Connection, data: BlockCreate) -> dict:
    if data.kind == "session":
        get_task(conn, data.task_id)  # 404 if missing
    start_min = parse_time_min(data.start) if data.start is not None else None
    end_min = (
        parse_time_min(data.end, allow_end_of_day=True) if data.end is not None else None
    )
    return _insert_block(
        conn,
        title=data.title,
        kind=data.kind,
        task_id=data.task_id,
        date=data.date,
        start_min=start_min,
        end_min=end_min,
        notes=data.notes,
        allow_overlap=data.allow_overlap,
    )


def create_session(
    conn: sqlite3.Connection, task_id: str, data: SessionCreate
) -> dict:
    task = get_task(conn, task_id)
    start_min = (
        parse_time_min(data.start)
        if data.start is not None and not data.all_day
        else None
    )
    end_min = (
        parse_time_min(data.end, allow_end_of_day=True)
        if data.end is not None and not data.all_day
        else None
    )
    return _insert_block(
        conn,
        title=task["title"],
        kind="session",
        task_id=task_id,
        date=data.date,
        start_min=start_min,
        end_min=end_min,
        notes=data.notes,
        allow_overlap=data.allow_overlap,
    )


def update_block(conn: sqlite3.Connection, block_id: str, data: BlockUpdate) -> dict:
    row = _get_row(conn, block_id)
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return _row_to_block(row)

    if "title" in fields and fields["title"] is None:
        raise bad_request("title must not be null")
    if "date" in fields and fields["date"] is None:
        raise bad_request("date must not be null")

    date = fields.get("date", row["date"])

    existing_start = (
        fmt_time(row["start_min"]) if row["start_min"] is not None else None
    )
    existing_end = fmt_time(row["end_min"]) if row["end_min"] is not None else None

    start = fields["start"] if "start" in fields else existing_start
    end = fields["end"] if "end" in fields else existing_end

    if start is None and end is None:
        start_min = end_min = None
    elif start is None or end is None:
        raise bad_request("start and end must be provided together (or both omitted)")
    else:
        start_min = parse_time_min(start)
        end_min = parse_time_min(end, allow_end_of_day=True)
        if start_min >= end_min:
            raise bad_request("start must be before end")

    schedule_changed = (
        date != row["date"] or start != existing_start or end != existing_end
    )
    if schedule_changed:
        _validate_block_time(conn, date, start_min, end_min)
        conflicts = find_conflicts(
            conn, date, start_min, end_min, exclude_block_id=block_id
        )
        if conflicts and not data.allow_overlap:
            raise AppError(
                409,
                "conflict",
                "This slot overlaps existing blocks. Choose another slot or pass allow_overlap.",
                conflicts,
            )

    with conn:
        conn.execute(
            """
            UPDATE blocks
               SET title = ?, date = ?, start_min = ?, end_min = ?, notes = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (
                fields.get("title", row["title"]),
                date,
                start_min,
                end_min,
                fields.get("notes", row["notes"]) or "",
                now_iso(),
                block_id,
            ),
        )
    return get_block(conn, block_id)


def delete_block(conn: sqlite3.Connection, block_id: str) -> None:
    _get_row(conn, block_id)
    with conn:
        conn.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
