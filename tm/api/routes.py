"""HTTP API routes."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse

from tm import __version__
from tm.config import llm_configured
from tm.dates import now_iso, parse_date, today
from tm.db import connect
from tm.errors import bad_request
from tm.models import (
    BlockCreate,
    BlockOut,
    BlockUpdate,
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


def get_conn(request: Request):
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def _range(from_value: str | None, to_value: str | None, conn: sqlite3.Connection) -> tuple[str, str]:
    settings = get_settings(conn)
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
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
) -> dict:
    try:
        from_iso, to_iso = _range(from_, to, conn)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    settings = get_settings(conn)
    return {
        "settings": settings.model_dump(),
        "tasks": list_tasks(conn),
        "blocks": list_blocks(conn, from_iso, to_iso),
        "today": today().isoformat(),
        "now": now_iso(),
    }


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks_route(
    conn: Conn,
    status_filter: str = Query("all", alias="status"),
    project: str | None = None,
) -> list[dict]:
    return list_tasks(conn, status=status_filter, project=project)


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task_route(data: TaskCreate, conn: Conn) -> dict:
    return create_task(conn, data)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task_route(task_id: str, conn: Conn) -> dict:
    return get_task(conn, task_id)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task_route(task_id: str, data: TaskUpdate, conn: Conn) -> dict:
    return update_task(conn, task_id, data)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_route(task_id: str, conn: Conn) -> Response:
    delete_task(conn, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tasks/{task_id}/sessions",
    response_model=BlockOut,
    status_code=status.HTTP_201_CREATED,
)
def schedule_session_route(task_id: str, data: SessionCreate, conn: Conn) -> dict:
    return create_session(conn, task_id, data)


@router.post("/blocks", response_model=BlockOut, status_code=status.HTTP_201_CREATED)
def create_block_route(data: BlockCreate, conn: Conn) -> dict:
    return create_block(conn, data)


@router.get("/blocks/{block_id}", response_model=BlockOut)
def get_block_route(block_id: str, conn: Conn) -> dict:
    return get_block(conn, block_id)


@router.patch("/blocks/{block_id}", response_model=BlockOut)
def update_block_route(block_id: str, data: BlockUpdate, conn: Conn) -> dict:
    return update_block(conn, block_id, data)


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block_route(block_id: str, conn: Conn) -> Response:
    delete_block(conn, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/free-slots")
def free_slots_route(
    conn: Conn,
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
def get_settings_route(conn: Conn) -> Settings:
    return get_settings(conn)


@router.patch("/settings", response_model=Settings)
def update_settings_route(data: SettingsUpdate, conn: Conn) -> Settings:
    return update_settings(conn, data)


@router.get("/export")
def export_route(conn: Conn) -> JSONResponse:
    return JSONResponse(
        {
            "version": __version__,
            "exported_at": now_iso(),
            "settings": get_settings(conn).model_dump(),
            "tasks": list_tasks(conn),
            "blocks": list_blocks(conn, "0001-01-01", "9999-12-31"),
        }
    )
