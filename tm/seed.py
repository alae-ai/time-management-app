"""Seed the database with a small demo schedule."""

from __future__ import annotations

from datetime import timedelta

import typer

from tm.dates import today
from tm.db import connect, init_db
from tm.models import BlockCreate, SessionCreate, TaskCreate
from tm.services.blocks import create_block, create_session
from tm.services.tasks import create_task

app = typer.Typer(add_completion=False)


@app.command()
def main(
    reset: bool = typer.Option(False, "--reset", help="Delete existing tasks and blocks first"),
) -> None:
    """Populate the local database with demo data."""
    init_db()
    conn = connect()
    try:
        if reset:
            with conn:
                conn.execute("DELETE FROM blocks")
                conn.execute("DELETE FROM tasks")

        existing = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if existing:
            typer.echo("Database already contains tasks; use --reset to replace them.")
            return

        day = today() + timedelta(days=2)
        task = create_task(
            conn,
            TaskCreate(
                title="TP report",
                project="TP",
                deadline=(day + timedelta(days=5)).isoformat(),
            ),
        )
        create_block(
            conn,
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
            task["id"],
            SessionCreate(date=day.isoformat(), start="17:30", end="19:00"),
        )
        typer.echo(f"Seeded demo data around {day.isoformat()}.")
    finally:
        conn.close()


if __name__ == "__main__":
    app()
