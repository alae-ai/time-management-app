"""Shared FastAPI dependencies for authentication and database connections."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import Depends, Request, Response

from tm.auth import (
    SESSION_COOKIE,
    get_api_token_user,
    get_session_user,
    row_to_user,
)
from tm.config import COOKIE_SECURE, SESSION_DAYS
from tm.db import connect
from tm.errors import AppError


def get_conn(request: Request):
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _raw_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    api_key = request.headers.get("x-api-key", "").strip()
    if api_key:
        return api_key
    return request.cookies.get(SESSION_COOKIE)


def _resolve_user(request: Request, conn: sqlite3.Connection) -> dict | None:
    raw_token = _raw_token(request)
    if not raw_token:
        return None
    row = get_api_token_user(conn, raw_token)
    if row is None:
        row = get_session_user(conn, raw_token)
    return row_to_user(row) if row is not None else None


def get_current_user(request: Request, conn: Conn) -> dict:
    user = _resolve_user(request, conn)
    if user is None:
        raise AppError(401, "unauthorized", "Authentication required.")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> dict:
    if not user["is_admin"]:
        raise AppError(403, "forbidden", "Administrator access required.")
    return user


AdminUser = Annotated[dict, Depends(require_admin)]


def get_optional_user(request: Request, conn: Conn) -> dict | None:
    return _resolve_user(request, conn)


OptionalUser = Annotated[dict | None, Depends(get_optional_user)]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
