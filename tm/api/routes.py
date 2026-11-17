"""HTTP API routes for the authenticated user's calendar."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import JSONResponse

from tm import __version__
from tm.api.deps import Conn, CurrentUser
from tm.config import llm_configured
from tm.dates import now_iso, parse_date, parse_time_min, today
from tm.errors import AppError, bad_request
from tm.models import (
    BlockCreate,
    BlockOut,
    BlockUpdate,
    ImportPayload,
    SessionCreate,
    Settings,
    SettingsUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from tm.services.blocks import (
    create_block,
    create_session,
    delete_block,
    get_block,
    list_blocks,
    update_block,
)
from tm.services.free_slots import find_free_slots
from tm.services.settings import get_settings, update_settings
from tm.services.tasks import (
    create_task,
    delete_task,
    get_task,
    list_tasks,
    update_task,
)

router = APIRouter()


def _import_date(value: str) -> str:
    try:
        return parse_date(value).isoformat()
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


def _import_time(value: str, *, end_of_day: bool = False) -> int:
    try:
        return parse_time_min(value, allow_end_of_day=end_of_day)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


def _range(
    from_value: str | None,
    to_value: str | None,
    conn,
    user_id: str,
) -> tuple[str, str]:
    settings = get_settings(conn, user_id)
    start = parse_date(from_value) if from_value else today()
    end = parse_date(to_value) if to_value else start + timedelta(days=30)
    if end < start:
        raise bad_request("'to' must be on or after 'from'")
    if (end - start).days + 1 > settings.max_range_days:
        raise bad_request(f"range must be at most {settings.max_range_days} days")
    return start.isoformat(), end.isoformat()


@router.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "now": now_iso(),
        "version": __version__,
        "llm_configured": llm_configured(),
    }


@router.get("/state")
def state(
    conn: Conn,
    user: CurrentUser,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
) -> dict:
    try:
        from_iso, to_iso = _range(from_, to, conn, user["id"])
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    settings = get_settings(conn, user["id"])
    return {
        "settings": settings.model_dump(),
        "tasks": list_tasks(conn, user["id"]),
        "blocks": list_blocks(conn, user["id"], from_iso, to_iso),
        "today": today().isoformat(),
        "now": now_iso(),
    }


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks_route(
    conn: Conn,
    user: CurrentUser,
    status_filter: str = Query("all", alias="status"),
    project: str | None = None,
) -> list[dict]:
    return list_tasks(conn, user["id"], status=status_filter, project=project)


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task_route(data: TaskCreate, conn: Conn, user: CurrentUser) -> dict:
    return create_task(conn, user["id"], data)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task_route(task_id: str, conn: Conn, user: CurrentUser) -> dict:
    return get_task(conn, user["id"], task_id)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task_route(
    task_id: str, data: TaskUpdate, conn: Conn, user: CurrentUser
) -> dict:
    return update_task(conn, user["id"], task_id, data)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_route(task_id: str, conn: Conn, user: CurrentUser) -> Response:
    delete_task(conn, user["id"], task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tasks/{task_id}/sessions",
    response_model=BlockOut,
    status_code=status.HTTP_201_CREATED,
)
def schedule_session_route(
    task_id: str, data: SessionCreate, conn: Conn, user: CurrentUser
) -> dict:
    return create_session(conn, user["id"], task_id, data)


@router.post("/blocks", response_model=BlockOut, status_code=status.HTTP_201_CREATED)
def create_block_route(data: BlockCreate, conn: Conn, user: CurrentUser) -> dict:
    return create_block(conn, user["id"], data)


@router.get("/blocks/{block_id}", response_model=BlockOut)
def get_block_route(block_id: str, conn: Conn, user: CurrentUser) -> dict:
    return get_block(conn, user["id"], block_id)


@router.patch("/blocks/{block_id}", response_model=BlockOut)
def update_block_route(
    block_id: str, data: BlockUpdate, conn: Conn, user: CurrentUser
) -> dict:
    return update_block(conn, user["id"], block_id, data)


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block_route(block_id: str, conn: Conn, user: CurrentUser) -> Response:
    delete_block(conn, user["id"], block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/free-slots")
def free_slots_route(
    conn: Conn,
    user: CurrentUser,
    from_: str = Query(alias="from"),
    to: str = Query(),
    min_minutes: int = Query(30, alias="min"),
    day_start: str | None = None,
    day_end: str | None = None,
    granularity: int | None = None,
    buffer: int | None = None,
    include_done: bool = False,
) -> dict:
    try:
        return find_free_slots(
            conn,
            user["id"],
            from_,
            to,
            min_minutes=min_minutes,
            day_start=day_start,
            day_end=day_end,
            granularity=granularity,
            buffer=buffer,
            include_done=include_done,
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


@router.get("/settings", response_model=Settings)
def get_settings_route(conn: Conn, user: CurrentUser) -> Settings:
    return get_settings(conn, user["id"])


@router.patch("/settings", response_model=Settings)
def update_settings_route(
    data: SettingsUpdate, conn: Conn, user: CurrentUser
) -> Settings:
    return update_settings(conn, user["id"], data)


@router.get("/export")
def export_route(conn: Conn, user: CurrentUser) -> JSONResponse:
    return JSONResponse(
        {
            "version": __version__,
            "exported_at": now_iso(),
            "settings": get_settings(conn, user["id"]).model_dump(),
            "tasks": list_tasks(conn, user["id"]),
            "blocks": list_blocks(conn, user["id"], "0001-01-01", "9999-12-31"),
        }
    )


@router.post("/import")
def import_route(data: ImportPayload, conn: Conn, user: CurrentUser) -> dict:
    """Import an export payload into the current account.

    This is intentionally additive by default. ``replace=true`` replaces only the
    current user's tasks and blocks, never another user's data.
    """
    user_id = user["id"]
    if data.settings is not None:
        update_settings(conn, user_id, SettingsUpdate(**data.settings.model_dump()))

    imported_tasks = 0
    imported_blocks = 0
    with conn:
        if data.replace:
            conn.execute("DELETE FROM blocks WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))

        for task in data.tasks:
            deadline = _import_date(task.deadline) if task.deadline else None
            deadline_min = (
                _import_time(task.deadline_time)
                if task.deadline_time is not None
                else None
            )
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO tasks
                  (id, user_id, title, project, notes, deadline_date, deadline_min,
                   done, done_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    user_id,
                    task.title,
                    task.project or None,
                    task.notes,
                    deadline,
                    deadline_min,
                    int(task.done),
                    task.done_at,
                    task.created_at,
                    task.updated_at,
                ),
            )
            if cursor.rowcount:
                imported_tasks += 1
            else:
                owner = conn.execute(
                    "SELECT user_id FROM tasks WHERE id = ?", (task.id,)
                ).fetchone()
                if owner is None or owner["user_id"] != user_id:
                    raise AppError(
                        409,
                        "import_conflict",
                        f"Task id {task.id!r} already belongs to another account.",
                    )

        for block in data.blocks:
            task_id = block.task_id
            if block.kind == "session":
                if not task_id:
                    raise bad_request("an imported session requires task_id")
                owned = conn.execute(
                    "SELECT 1 FROM tasks WHERE id = ? AND user_id = ?",
                    (task_id, user_id),
                ).fetchone()
                if owned is None:
                    raise bad_request(
                        f"Imported session {block.id!r} references a task outside this account."
                    )
            block_date = _import_date(block.date)
            start_min = None
            end_min = None
            if not block.all_day:
                if block.start is None or block.end is None:
                    raise bad_request(
                        f"Imported block {block.id!r} needs start and end or all_day."
                    )
                start_min = _import_time(block.start)
                end_min = _import_time(block.end, end_of_day=True)
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO blocks
                  (id, user_id, title, kind, task_id, date, start_min, end_min,
                   notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    block.id,
                    user_id,
                    block.title,
                    block.kind,
                    task_id,
                    block_date,
                    start_min,
                    end_min,
                    block.notes,
                    block.created_at,
                    block.updated_at,
                ),
            )
            if cursor.rowcount:
                imported_blocks += 1
            else:
                owner = conn.execute(
                    "SELECT user_id FROM blocks WHERE id = ?", (block.id,)
                ).fetchone()
                if owner is None or owner["user_id"] != user_id:
                    raise AppError(
                        409,
                        "import_conflict",
                        f"Block id {block.id!r} already belongs to another account.",
                    )

    return {
        "imported_tasks": imported_tasks,
        "imported_blocks": imported_blocks,
        "replaced": data.replace,
    }
