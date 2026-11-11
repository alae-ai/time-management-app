from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from tm.api.app import create_app
from tm.dates import today
from tm.db import connect, init_db


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "free.db"
    init_db(path)
    connection = connect(path)
    yield connection
    connection.close()


@pytest.fixture
def future_day():
    return today() + timedelta(days=30)
