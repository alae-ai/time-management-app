"""Authentication, account, token, and admin routes."""

from __future__ import annotations

import threading

from fastapi import APIRouter, Request, Response, status

from tm.api.deps import (
    AdminUser,
    Conn,
    CurrentUser,
    OptionalUser,
    clear_session_cookie,
    client_ip,
    set_session_cookie,
)
from tm.auth import (
    SESSION_COOKIE,
    authenticate,
    change_password,
    claim_legacy_data,
    create_api_token,
    create_session,
    create_user,
    delete_session,
    list_api_tokens,
    list_users,
    revoke_api_token,
    row_to_user,
    setup_required,
    update_user,
)
from tm.config import SETUP_TOKEN
from tm.errors import AppError, bad_request
from tm.models import (
    AdminUserCreate,
    AdminUserUpdate,
    AuthSession,
    LoginRequest,
    PasswordChange,
    SetupRequest,
    TokenCreate,
    TokenCreated,
    TokenOut,
    UserOut,
)

router = APIRouter()
_setup_lock = threading.Lock()


def _check_setup_token(token: str | None) -> None:
    if SETUP_TOKEN and (token or "") != SETUP_TOKEN:
        raise AppError(403, "invalid_setup_token", "The setup token is incorrect.")


@router.get("/auth/session", response_model=AuthSession)
def session_route(conn: Conn, user: OptionalUser) -> dict:
    needs_setup = setup_required(conn)
    return {
        "authenticated": user is not None,
        "setup_required": needs_setup,
        "user": user if user is not None else None,
    }


@router.post("/auth/setup", response_model=AuthSession, status_code=status.HTTP_201_CREATED)
def setup_route(
    data: SetupRequest,
    conn: Conn,
    request: Request,
    response: Response,
) -> dict:
    with _setup_lock:
        if not setup_required(conn):
            raise AppError(
                409, "setup_complete", "The administrator account already exists."
            )
        _check_setup_token(data.setup_token)
        user = create_user(
            conn,
            email=data.email,
            name=data.name,
            password=data.password,
            is_admin=True,
        )
        claim_legacy_data(conn, user["id"])
        raw_token, _ = create_session(
            conn,
            user["id"],
            user_agent=request.headers.get("user-agent"),
            ip=client_ip(request),
        )
        set_session_cookie(response, raw_token)
        return {"authenticated": True, "setup_required": False, "user": user}


@router.post("/auth/login", response_model=AuthSession)
def login_route(
    data: LoginRequest,
    conn: Conn,
    request: Request,
    response: Response,
) -> dict:
    row = authenticate(conn, data.email, data.password)
    if row is None:
        raise AppError(401, "invalid_credentials", "Email or password is incorrect.")
    user = row_to_user(row)
    raw_token, _ = create_session(
        conn,
        user["id"],
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
    )
    set_session_cookie(response, raw_token)
    return {"authenticated": True, "setup_required": False, "user": user}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_route(request: Request, conn: Conn, response: Response) -> Response:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        delete_session(conn, raw_token)
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/auth/me", response_model=UserOut)
def me_route(user: CurrentUser) -> dict:
    return user


@router.post("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
def password_route(data: PasswordChange, user: CurrentUser, conn: Conn) -> Response:
    change_password(conn, user["id"], data.current_password, data.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/tokens", response_model=list[TokenOut])
def list_tokens_route(user: CurrentUser, conn: Conn) -> list[dict]:
    return list_api_tokens(conn, user["id"])


@router.post("/auth/tokens", response_model=TokenCreated, status_code=status.HTTP_201_CREATED)
def create_token_route(data: TokenCreate, user: CurrentUser, conn: Conn) -> dict:
    raw_token, token = create_api_token(conn, user["id"], data.name)
    return {**token, "token": raw_token}


@router.delete("/auth/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_token_route(token_id: str, user: CurrentUser, conn: Conn) -> Response:
    revoke_api_token(conn, user["id"], token_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/users", response_model=list[UserOut])
def admin_users_route(admin: AdminUser, conn: Conn) -> list[dict]:
    return list_users(conn)


@router.post("/admin/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def admin_create_user_route(
    data: AdminUserCreate, admin: AdminUser, conn: Conn
) -> dict:
    return create_user(
        conn,
        email=data.email,
        name=data.name,
        password=data.password,
        is_admin=data.is_admin,
    )


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def admin_update_user_route(
    user_id: str, data: AdminUserUpdate, admin: AdminUser, conn: Conn
) -> dict:
    if user_id == admin["id"] and data.is_active is False:
        raise bad_request("you cannot deactivate your own account")
    return update_user(
        conn,
        user_id,
        name=data.name,
        is_admin=data.is_admin,
        is_active=data.is_active,
        password=data.password,
    )
