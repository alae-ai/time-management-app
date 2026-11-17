"""Users, password hashing, browser sessions, and personal API tokens."""

from __future__ import annotations

import base64
import hashlib
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

from tm.config import SESSION_DAYS
from tm.errors import AppError, bad_request, not_found
from tm.services.settings import seed_defaults

LEGACY_USER_ID = "legacy-user"
SESSION_COOKIE = "tm_session"
API_TOKEN_PREFIX = "tm_"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    try:
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=64,
            maxmem=64 * 1024 * 1024,
        )
        return f"scrypt$16384$8$1${_b64(salt)}${_b64(digest)}"
    except (ValueError, MemoryError):
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, 600_000, dklen=64
        )
        return f"pbkdf2$600000${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        if not encoded or encoded == "!":
            return False
        parts = encoded.split("$")
        if parts[0] == "scrypt" and len(parts) == 6:
            _, n, r, p, salt_b64, digest_b64 = parts
            digest = hashlib.scrypt(
                password.encode("utf-8"),
                salt=_unb64(salt_b64),
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(_unb64(digest_b64)),
                maxmem=64 * 1024 * 1024,
            )
            return secrets.compare_digest(digest, _unb64(digest_b64))
        if parts[0] == "pbkdf2" and len(parts) == 4:
            _, iterations, salt_b64, digest_b64 = parts
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                _unb64(salt_b64),
                int(iterations),
                dklen=len(_unb64(digest_b64)),
            )
            return secrets.compare_digest(digest, _unb64(digest_b64))
    except (ValueError, TypeError):
        return False
    return False


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def row_to_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "is_admin": bool(row["is_admin"]),
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_login_at": row["last_login_at"],
    }


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise not_found("user", user_id)
    return row


def get_user_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
        (normalize_email(email),),
    ).fetchone()


def list_users(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM users
        WHERE id != ?
        ORDER BY is_active DESC, email
        """,
        (LEGACY_USER_ID,),
    ).fetchall()
    return [row_to_user(row) for row in rows]


def create_user(
    conn: sqlite3.Connection,
    *,
    email: str,
    name: str,
    password: str,
    is_admin: bool = False,
) -> dict:
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat(timespec="seconds")
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO users
                  (id, email, name, password_hash, is_admin, is_active,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    user_id,
                    normalize_email(email),
                    name.strip(),
                    hash_password(password),
                    int(is_admin),
                    now,
                    now,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise AppError(409, "email_taken", "An account with that email already exists.") from exc
    seed_defaults(conn, user_id)
    return row_to_user(get_user_by_id(conn, user_id))


def authenticate(conn: sqlite3.Connection, email: str, password: str) -> sqlite3.Row | None:
    row = get_user_by_email(conn, email)
    if row is None or not row["is_active"] or row["id"] == LEGACY_USER_ID:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    with conn:
        conn.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), datetime.now().isoformat(timespec="seconds"), row["id"]),
        )
    return get_user_by_id(conn, row["id"])


def update_user(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    name: str | None = None,
    is_admin: bool | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> dict:
    row = get_user_by_id(conn, user_id)
    if row["id"] == LEGACY_USER_ID:
        raise bad_request("the legacy user cannot be modified")

    will_be_admin = bool(row["is_admin"]) if is_admin is None else is_admin
    will_be_active = bool(row["is_active"]) if is_active is None else is_active
    if row["is_admin"] and row["is_active"] and (not will_be_admin or not will_be_active):
        active_admins = conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_admin = 1 AND is_active = 1 AND id != ?",
            (LEGACY_USER_ID,),
        ).fetchone()[0]
        if active_admins == 0:
            raise bad_request("there must be at least one active admin")

    fields: list[str] = []
    params: list[object] = []
    if name is not None:
        fields.append("name = ?")
        params.append(name.strip())
    if is_admin is not None:
        fields.append("is_admin = ?")
        params.append(int(is_admin))
    if is_active is not None:
        fields.append("is_active = ?")
        params.append(int(is_active))
    if password is not None:
        fields.append("password_hash = ?")
        params.append(hash_password(password))
    if not fields:
        return row_to_user(row)

    fields.append("updated_at = ?")
    params.append(datetime.now().isoformat(timespec="seconds"))
    params.append(user_id)
    with conn:
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
    return row_to_user(get_user_by_id(conn, user_id))


def setup_required(conn: sqlite3.Connection) -> bool:
    count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE id != ? AND is_active = 1",
        (LEGACY_USER_ID,),
    ).fetchone()[0]
    return count == 0


def claim_legacy_data(conn: sqlite3.Connection, user_id: str) -> None:
    legacy = conn.execute(
        "SELECT id FROM users WHERE id = ?", (LEGACY_USER_ID,)
    ).fetchone()
    if legacy is None:
        return
    with conn:
        conn.execute(
            """
            INSERT INTO app_settings (user_id, key, value)
            SELECT ?, key, value FROM app_settings WHERE user_id = ?
            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
            """,
            (user_id, LEGACY_USER_ID),
        )
        conn.execute(
            "UPDATE tasks SET user_id = ? WHERE user_id = ?", (user_id, LEGACY_USER_ID)
        )
        conn.execute(
            "UPDATE blocks SET user_id = ? WHERE user_id = ?", (user_id, LEGACY_USER_ID)
        )
        conn.execute(
            "UPDATE conversations SET user_id = ? WHERE user_id = ?",
            (user_id, LEGACY_USER_ID),
        )
        conn.execute("DELETE FROM users WHERE id = ?", (LEGACY_USER_ID,))
    seed_defaults(conn, user_id)


def create_session(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, str]:
    now = datetime.now(UTC)
    expires = now + timedelta(days=SESSION_DAYS)
    raw_token = secrets.token_urlsafe(48)
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_now_utc(),))
        conn.execute(
            """
            INSERT INTO sessions
              (id, user_id, token_hash, created_at, expires_at, last_seen_at,
               user_agent, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user_id,
                _hash_token(raw_token),
                now.isoformat(timespec="seconds"),
                expires.isoformat(timespec="seconds"),
                now.isoformat(timespec="seconds"),
                user_agent,
                ip,
            ),
        )
    return raw_token, expires.isoformat(timespec="seconds")


def get_session_user(conn: sqlite3.Connection, raw_token: str) -> sqlite3.Row | None:
    if not raw_token:
        return None
    row = conn.execute(
        """
        SELECT u.* FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1
          AND u.id != ?
        """,
        (_hash_token(raw_token), _now_utc(), LEGACY_USER_ID),
    ).fetchone()
    return row


def delete_session(conn: sqlite3.Connection, raw_token: str) -> None:
    if not raw_token:
        return
    with conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(raw_token),))


def create_api_token(
    conn: sqlite3.Connection, user_id: str, name: str
) -> tuple[str, dict]:
    raw_token = f"{API_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    token_id = str(uuid.uuid4())
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            """
            INSERT INTO api_tokens
              (id, user_id, name, token_hash, created_at, last_used_at, expires_at)
            VALUES (?, ?, ?, ?, ?, NULL, NULL)
            """,
            (token_id, user_id, name, _hash_token(raw_token), now),
        )
    return raw_token, get_api_token(conn, user_id, token_id)


def get_api_token(conn: sqlite3.Connection, user_id: str, token_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM api_tokens WHERE id = ? AND user_id = ?",
        (token_id, user_id),
    ).fetchone()
    if row is None:
        raise not_found("API token", token_id)
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
        "expires_at": row["expires_at"],
    }


def list_api_tokens(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM api_tokens
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "expires_at": row["expires_at"],
        }
        for row in rows
    ]


def revoke_api_token(conn: sqlite3.Connection, user_id: str, token_id: str) -> None:
    get_api_token(conn, user_id, token_id)
    with conn:
        conn.execute(
            "DELETE FROM api_tokens WHERE id = ? AND user_id = ?", (token_id, user_id)
        )


def get_api_token_user(conn: sqlite3.Connection, raw_token: str) -> sqlite3.Row | None:
    if not raw_token:
        return None
    row = conn.execute(
        """
        SELECT u.* FROM api_tokens a
        JOIN users u ON u.id = a.user_id
        WHERE a.token_hash = ? AND u.is_active = 1 AND u.id != ?
          AND (a.expires_at IS NULL OR a.expires_at > ?)
        """,
        (_hash_token(raw_token), LEGACY_USER_ID, _now_utc()),
    ).fetchone()
    if row is not None:
        with conn:
            conn.execute(
                "UPDATE api_tokens SET last_used_at = ? WHERE token_hash = ?",
                (datetime.now().isoformat(timespec="seconds"), _hash_token(raw_token)),
            )
    return row


def change_password(
    conn: sqlite3.Connection,
    user_id: str,
    current_password: str,
    new_password: str,
) -> None:
    row = get_user_by_id(conn, user_id)
    if not verify_password(current_password, row["password_hash"]):
        raise bad_request("current password is incorrect")
    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (
                hash_password(new_password),
                datetime.now().isoformat(timespec="seconds"),
                user_id,
            ),
        )
