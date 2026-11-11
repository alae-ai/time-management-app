"""SQLite connections and migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tm.config import DB_PATH

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    conn = connect(db_path)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            number = int(migration.name.split("_", 1)[0])
            if number <= version:
                continue
            conn.executescript(migration.read_text(encoding="utf-8"))
            conn.execute(f"PRAGMA user_version = {number}")
            conn.commit()
        from tm.services.settings import seed_defaults

        seed_defaults(conn)
    finally:
        conn.close()


def user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])
