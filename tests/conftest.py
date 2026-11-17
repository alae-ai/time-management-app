from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from tm.api.app import create_app
from tm.auth import create_user
from tm.dates import today
from tm.db import connect, init_db

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-password-123"


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=tmp_path / "test.db")
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/auth/setup",
            json={
                "email": ADMIN_EMAIL,
                "name": "Admin",
                "password": ADMIN_PASSWORD,
            },
        )
        assert response.status_code == 201, response.text
        yield test_client


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "free.db"
    init_db(path)
    connection = connect(path)
    yield connection
    connection.close()


@pytest.fixture
def user(conn):
    return create_user(
        conn,
        email="user@example.com",
        name="User",
        password="user-password-123",
    )


@pytest.fixture
def future_day():
    return today() + timedelta(days=30)
