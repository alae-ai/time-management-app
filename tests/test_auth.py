from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from tm.api.app import create_app
from tm.auth import hash_password
from tm.db import init_db

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-password-123"
USER_EMAIL = "user@example.com"
USER_PASSWORD = "user-password-123"


def _new_client(app: TestClient) -> TestClient:
    return TestClient(app.app)


def test_unauthenticated_requests_are_rejected(client):
    with _new_client(client) as anonymous:
        response = anonymous.get("/api/tasks")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


def test_setup_status_and_login_logout(tmp_path):
    app = create_app(db_path=tmp_path / "auth.db")
    with TestClient(app) as client:
        status = client.get("/api/auth/session").json()
        assert status["setup_required"] is True
        assert status["authenticated"] is False

        setup = client.post(
            "/api/auth/setup",
            json={"email": ADMIN_EMAIL, "name": "Admin", "password": ADMIN_PASSWORD},
        )
        assert setup.status_code == 201, setup.text
        assert setup.json()["user"]["email"] == ADMIN_EMAIL
        assert setup.json()["user"]["is_admin"] is True
        assert client.get("/api/auth/session").json()["setup_required"] is False

        again = client.post(
            "/api/auth/setup",
            json={"email": "other@example.com", "password": ADMIN_PASSWORD},
        )
        assert again.status_code == 409

        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/session").json()["authenticated"] is False

        bad = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrong-password"},
        )
        assert bad.status_code == 401

        good = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert good.status_code == 200
        assert good.json()["user"]["email"] == ADMIN_EMAIL


def test_admin_creates_user_and_data_is_isolated(client):
    created = client.post(
        "/api/admin/users",
        json={
            "email": USER_EMAIL,
            "name": "User",
            "password": USER_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["is_admin"] is False

    admin_task = client.post("/api/tasks", json={"title": "Admin task"})
    assert admin_task.status_code == 201

    with _new_client(client) as user_client:
        login = user_client.post(
            "/api/auth/login",
            json={"email": USER_EMAIL, "password": USER_PASSWORD},
        )
        assert login.status_code == 200

        user_tasks = user_client.get("/api/tasks")
        assert user_tasks.status_code == 200
        assert user_tasks.json() == []

        assert user_client.post("/api/tasks", json={"title": "User task"}).status_code == 201
        user_ids = {task["title"] for task in user_client.get("/api/tasks").json()}
        assert user_ids == {"User task"}

        forbidden = user_client.get("/api/admin/users")
        assert forbidden.status_code == 403

        other = user_client.get(f"/api/tasks/{admin_task.json()['id']}")
        assert other.status_code == 404

    admin_titles = {task["title"] for task in client.get("/api/tasks").json()}
    assert admin_titles == {"Admin task"}


def test_api_token_authentication_and_revocation(client):
    created = client.post("/api/auth/tokens", json={"name": "test"})
    assert created.status_code == 201, created.text
    raw_token = created.json()["token"]
    token_id = created.json()["id"]

    with TestClient(client.app) as token_client:
        headers = {"Authorization": f"Bearer {raw_token}"}
        me = token_client.get("/api/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email"] == ADMIN_EMAIL
        assert token_client.get("/api/tasks", headers=headers).status_code == 200

        assert client.delete(f"/api/auth/tokens/{token_id}").status_code == 204
        assert token_client.get("/api/auth/me", headers=headers).status_code == 401


def test_password_change(client):
    changed = client.post(
        "/api/auth/password",
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "new-admin-password-123",
        },
    )
    assert changed.status_code == 204
    assert client.post("/api/auth/logout").status_code == 204
    login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": "new-admin-password-123"},
    )
    assert login.status_code == 200


def test_deactivated_user_cannot_login(client):
    client.post(
        "/api/admin/users",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
    )
    users = client.get("/api/admin/users").json()
    user_id = next(user["id"] for user in users if user["email"] == USER_EMAIL)
    assert client.patch(f"/api/admin/users/{user_id}", json={"is_active": False}).status_code == 200
    with _new_client(client) as user_client:
        login = user_client.post(
            "/api/auth/login",
            json={"email": USER_EMAIL, "password": USER_PASSWORD},
        )
        assert login.status_code == 401


def test_legacy_single_user_data_is_claimed_by_first_admin(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        (Path(__file__).resolve().parent.parent / "tm/migrations/001_init.sql").read_text()
    )
    conn.execute("PRAGMA user_version = 1")
    now = "2026-11-17T10:00:00"
    conn.execute(
        """
        INSERT INTO tasks
          (id, title, project, notes, deadline_date, deadline_min, done, done_at,
           created_at, updated_at)
        VALUES ('legacy-task', 'Old task', 'TP', '', '2026-12-02', NULL, 0, NULL, ?, ?)
        """,
        (now, now),
    )
    conn.execute(
        """
        INSERT INTO blocks
          (id, title, kind, task_id, date, start_min, end_min, notes,
           created_at, updated_at)
        VALUES ('legacy-block', 'Old block', 'appointment', NULL, '2026-12-01',
                540, 600, '', ?, ?)
        """,
        (now, now),
    )
    conn.commit()
    conn.close()

    init_db(path)

    app = create_app(db_path=path)
    with TestClient(app) as client:
        assert client.get("/api/auth/session").json()["setup_required"] is True
        setup = client.post(
            "/api/auth/setup",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert setup.status_code == 201, setup.text
        tasks = client.get("/api/tasks").json()
        assert [task["title"] for task in tasks] == ["Old task"]
        blocks = client.get(
            "/api/state",
            params={"from": "2026-12-01", "to": "2026-12-01"},
        ).json()["blocks"]
        assert [block["title"] for block in blocks] == ["Old block"]


def test_setup_token_is_required_when_configured(tmp_path, monkeypatch):
    import tm.api.auth_routes as auth_routes

    monkeypatch.setattr(auth_routes, "SETUP_TOKEN", "setup-secret")
    app = create_app(db_path=tmp_path / "setup-token.db")
    with TestClient(app) as client:
        denied = client.post(
            "/api/auth/setup",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert denied.status_code == 403
        allowed = client.post(
            "/api/auth/setup",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "setup_token": "setup-secret",
            },
        )
        assert allowed.status_code == 201


def test_import_into_current_account(client):
    payload = {
        "settings": {
            "day_start": "09:00",
            "day_end": "18:00",
            "week_starts_on": 1,
            "granularity_min": 30,
            "buffer_min": 0,
            "max_range_days": 366,
            "max_chat_messages": 40,
        },
        "tasks": [
            {
                "id": "imported-task",
                "title": "Imported task",
                "project": "TP",
                "notes": "",
                "deadline": "2026-12-02",
                "deadline_time": None,
                "done": False,
                "done_at": None,
                "created_at": "2026-11-17T10:00:00",
                "updated_at": "2026-11-17T10:00:00",
            }
        ],
        "blocks": [
            {
                "id": "imported-block",
                "title": "Imported task",
                "kind": "session",
                "task_id": "imported-task",
                "date": "2026-12-01",
                "start": "09:00",
                "end": "10:00",
                "all_day": False,
                "notes": "",
                "created_at": "2026-11-17T10:00:00",
                "updated_at": "2026-11-17T10:00:00",
            }
        ],
    }
    imported = client.post("/api/import", json=payload)
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported_tasks"] == 1
    assert imported.json()["imported_blocks"] == 1

    tasks = client.get("/api/tasks").json()
    assert [task["title"] for task in tasks] == ["Imported task"]
    state = client.get(
        "/api/state", params={"from": "2026-12-01", "to": "2026-12-01"}
    ).json()
    assert [block["title"] for block in state["blocks"]] == ["Imported task"]
    assert state["settings"]["day_start"] == "09:00"


def test_hash_password_round_trip():
    encoded = hash_password("a-long-password")
    from tm.auth import verify_password

    assert verify_password("a-long-password", encoded)
    assert not verify_password("wrong-password", encoded)
