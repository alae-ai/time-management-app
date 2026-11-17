"""Seed the database with a small demo schedule for one user."""

from __future__ import annotations

from datetime import timedelta

import typer

from tm.auth import claim_legacy_data, create_user, get_user_by_email, list_users
from tm.dates import today
from tm.db import connect, init_db
from tm.models import BlockCreate, SessionCreate, TaskCreate
from tm.services.blocks import create_block, create_session
from tm.services.tasks import create_task

app = typer.Typer(add_completion=False)

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password-123"


@app.command()
def main(
    reset: bool = typer.Option(False, "--reset", help="Delete this user's tasks and blocks first"),
    email: str | None = typer.Option(None, "--email", help="Account to seed"),
) -> None:
    """Populate a user's calendar with demo data."""
    init_db()
    conn = connect()
    try:
        if email:
            row = get_user_by_email(conn, email)
            if row is None or row["id"] == "legacy-user":
                typer.secho(f"No active account for {email!r}.", fg="red", err=True)
                raise typer.Exit(1)
            user = {"id": row["id"], "email": row["email"]}
        else:
            users = list_users(conn)
            if users:
                user = users[0]
            else:
                user = create_user(
                    conn,
                    email=DEMO_EMAIL,
                    name="Demo",
                    password=DEMO_PASSWORD,
                    is_admin=True,
                )
                claim_legacy_data(conn, user["id"])
                typer.echo(
                    f"Created demo admin {DEMO_EMAIL} with password {DEMO_PASSWORD!r}."
                )

        user_id = user["id"]
        if reset:
            with conn:
                conn.execute("DELETE FROM blocks WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))

        existing = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        if existing:
            typer.echo("This account already contains tasks; use --reset to replace them.")
            return

        day = today() + timedelta(days=2)
        task = create_task(
            conn,
            user_id,
            TaskCreate(
                title="TP report",
                project="TP",
                deadline=(day + timedelta(days=5)).isoformat(),
            ),
        )
        create_block(
            conn,
            user_id,
            BlockCreate(
                title="Dentist",
                kind="appointment",
                date=day.isoformat(),
                start="09:00",
                end="10:00",
            ),
        )
        create_block(
            conn,
            user_id,
            BlockCreate(
                title="Lecture",
                kind="appointment",
                date=day.isoformat(),
                start="14:00",
                end="16:00",
            ),
        )
        create_session(
            conn,
            user_id,
            task["id"],
            SessionCreate(date=day.isoformat(), start="17:30", end="19:00"),
        )
        typer.echo(f"Seeded demo data for {user['email']} around {day.isoformat()}.")
    finally:
        conn.close()


if __name__ == "__main__":
    app()
