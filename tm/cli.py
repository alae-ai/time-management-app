"""Command-line client for the local time-management API."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import httpx
import typer

from tm.config import API_URL, HOST, PORT
from tm.dates import fmt_date, fmt_duration, parse_date, today

app = typer.Typer(
    help="Local time-management client. Requires the API to be running.",
    no_args_is_help=True,
    add_completion=False,
)
settings_app = typer.Typer(help="Show or change calendar preferences.", no_args_is_help=False)
task_app = typer.Typer(help="Create and complete tasks.", no_args_is_help=True)
appointment_app = typer.Typer(help="Create appointments.", no_args_is_help=True)

app.add_typer(settings_app, name="settings")
app.add_typer(task_app, name="task")
app.add_typer(appointment_app, name="appointment")


def _short(ident: str) -> str:
    return ident[:8]


def _parse_date_or_exit(value: str, label: str):
    try:
        return parse_date(value)
    except ValueError as exc:
        typer.secho(f"Invalid {label}: {exc}", fg="red", err=True)
        raise typer.Exit(1) from exc


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    url = f"{API_URL.rstrip('/')}{path}"
    try:
        return httpx.request(method, url, json=body, params=params, timeout=20)
    except httpx.HTTPError as exc:
        typer.secho(
            f"Cannot reach the app at {API_URL}. Start it with `tm serve` or `scripts/dev.sh`.",
            fg="red",
            err=True,
        )
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(1) from exc


def _call(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    response = _request(method, path, body=body, params=params)
    if response.status_code == 204:
        return None
    if response.status_code >= 400:
        message = response.text
        details: Any = None
        try:
            payload = response.json()
            error = payload.get("error", {})
            message = error.get("message", message)
            details = error.get("details")
        except ValueError:
            pass
        typer.secho(f"Error ({response.status_code}): {message}", fg="red", err=True)
        if details:
            typer.echo(json.dumps(details, indent=2), err=True)
        raise typer.Exit(1)
    try:
        return response.json()
    except ValueError:
        return None


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2))


def _print_task(task: dict[str, Any]) -> None:
    mark = "[x]" if task["done"] else "[ ]"
    if task["deadline"]:
        due = fmt_date(task["deadline"])
        if task["deadline_time"]:
            due += f" {task['deadline_time']}"
    else:
        due = "backlog"
    project = f" [{task['project']}]" if task["project"] else ""
    typer.echo(f"  {mark} {due}  {task['title']}{project}  {_short(task['id'])}")


def _print_block(block: dict[str, Any]) -> None:
    when = fmt_date(block["date"])
    if block["all_day"]:
        time = "all day"
    else:
        time = f"{block['start']}–{block['end']}"
    typer.echo(f"  {when}  {time}  {block['title']}  {_short(block['id'])}")


def _print_settings(settings: dict[str, Any], as_json: bool) -> None:
    if as_json:
        _print_json(settings)
        return
    typer.echo(f"day_start        {settings['day_start']}")
    typer.echo(f"day_end          {settings['day_end']}")
    typer.echo(f"week_starts_on   {settings['week_starts_on']} (0=Sunday, 1=Monday)")
    typer.echo(f"granularity_min  {settings['granularity_min']}")
    typer.echo(f"buffer_min       {settings['buffer_min']}")
    typer.echo(f"max_range_days   {settings['max_range_days']}")


@app.command()
def health(as_json: bool = typer.Option(False, "--json")) -> None:
    """Check that the API is reachable."""
    data = _call("GET", "/api/health")
    if as_json:
        _print_json(data)
    else:
        typer.echo(f"ok · v{data['version']} · {data['now']}")
        typer.echo(f"llm configured: {'yes' if data['llm_configured'] else 'no'}")


@app.command()
def serve(
    port: int = typer.Option(PORT, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Run the API server (development)."""
    import uvicorn

    uvicorn.run("tm.api.app:app", host=HOST, port=port, reload=reload)


@app.command("state")
def show_state(
    from_: str | None = typer.Option(None, "--from", help="YYYY-MM-DD or DD/MM/YYYY"),
    to: str | None = typer.Option(None, "--to", help="YYYY-MM-DD or DD/MM/YYYY"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show tasks and calendar blocks."""
    params = {}
    if from_:
        params["from"] = from_
    if to:
        params["to"] = to
    data = _call("GET", "/api/state", params=params or None)
    if as_json:
        _print_json(data)
        return

    settings = data["settings"]
    typer.echo(
        f"Window {settings['day_start']}–{settings['day_end']} · "
        f"granularity {settings['granularity_min']}m"
    )
    open_tasks = [task for task in data["tasks"] if not task["done"]]
    typer.echo(f"Tasks ({len(open_tasks)} open)")
    for task in data["tasks"]:
        _print_task(task)
    typer.echo(f"Blocks ({len(data['blocks'])})")
    for block in data["blocks"]:
        _print_block(block)


@app.command()
def slots(
    from_: str | None = typer.Option(None, "--from", help="defaults to today"),
    to: str | None = typer.Option(None, "--to", help="defaults to 14 days out"),
    min_minutes: int = typer.Option(30, "--min", "-m", help="minimum useful duration"),
    day_start: str | None = typer.Option(None, "--day-start"),
    day_end: str | None = typer.Option(None, "--day-end"),
    granularity: int | None = typer.Option(None, "--granularity"),
    buffer: int | None = typer.Option(None, "--buffer"),
    include_done: bool = typer.Option(False, "--include-done"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List free gaps in the schedule."""
    start = _parse_date_or_exit(from_, "from date") if from_ else today()
    end = _parse_date_or_exit(to, "to date") if to else start + timedelta(days=14)
    params: dict[str, Any] = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "min": min_minutes,
    }
    if day_start:
        params["day_start"] = day_start
    if day_end:
        params["day_end"] = day_end
    if granularity is not None:
        params["granularity"] = granularity
    if buffer is not None:
        params["buffer"] = buffer
    if include_done:
        params["include_done"] = True

    data = _call("GET", "/api/free-slots", params=params)
    if as_json:
        _print_json(data)
        return

    window = data["window"]
    typer.echo(
        f"Free slots · {fmt_date(data['from'])} → {fmt_date(data['to'])} · "
        f"min {data['min_minutes']}m · window {window['start']}–{window['end']}"
    )
    if not data["slots"]:
        typer.echo("  No free slots match.")
        return
    for slot in data["slots"]:
        when = fmt_date(slot["date"])
        if slot["all_day"]:
            label = f"all day ({window['start']}–{window['end']})"
        else:
            label = f"{slot['start']}–{slot['end']}"
        typer.echo(f"  {when}  {label}  {fmt_duration(slot['minutes'])}")
    if data.get("truncated"):
        typer.echo("  … list truncated")


@app.command()
def tasks(
    open_only: bool = typer.Option(False, "--open"),
    project: str | None = typer.Option(None, "--project"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List tasks."""
    params: dict[str, Any] = {"status": "open" if open_only else "all"}
    if project:
        params["project"] = project
    data = _call("GET", "/api/tasks", params=params)
    if as_json:
        _print_json(data)
        return
    if not data:
        typer.echo("  No tasks.")
        return
    for task in data:
        _print_task(task)


@task_app.command("add")
def task_add(
    title: str = typer.Option(..., "--title", "-t"),
    deadline: str | None = typer.Option(None, "--deadline", "-d"),
    deadline_time: str | None = typer.Option(None, "--deadline-time"),
    project: str | None = typer.Option(None, "--project", "-p"),
    notes: str = typer.Option("", "--notes"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Create a task."""
    body = {
        "title": title,
        "deadline": deadline,
        "deadline_time": deadline_time,
        "project": project,
        "notes": notes,
    }
    data = _call("POST", "/api/tasks", body=body)
    if as_json:
        _print_json(data)
        return
    typer.echo(f"Created task {_short(data['id'])}: {data['title']}")
    _print_task(data)


@task_app.command("done")
def task_done(
    task_id: str = typer.Argument(...),
    undo: bool = typer.Option(False, "--undo"),
) -> None:
    """Mark a task done (or undo it)."""
    data = _call(
        "PATCH",
        f"/api/tasks/{task_id}",
        body={"done": not undo},
    )
    state = "done" if data["done"] else "open"
    typer.echo(f"Task {_short(data['id'])} is now {state}: {data['title']}")


@appointment_app.command("add")
def appointment_add(
    title: str = typer.Option(..., "--title", "-t"),
    date: str = typer.Option(..., "--date", "-d"),
    start: str | None = typer.Option(None, "--start"),
    end: str | None = typer.Option(None, "--end"),
    notes: str = typer.Option("", "--notes"),
    allow_overlap: bool = typer.Option(False, "--allow-overlap"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Create an appointment."""
    if (start is None) != (end is None):
        raise typer.BadParameter("--start and --end must be provided together")
    body = {
        "title": title,
        "kind": "appointment",
        "date": date,
        "start": start,
        "end": end,
        "notes": notes,
        "allow_overlap": allow_overlap,
    }
    data = _call("POST", "/api/blocks", body=body)
    if as_json:
        _print_json(data)
        return
    typer.echo(f"Created appointment {_short(data['id'])}")
    _print_block(data)


@app.command()
def schedule(
    task_id: str = typer.Option(..., "--task", "-t"),
    date: str = typer.Option(..., "--date", "-d"),
    start: str | None = typer.Option(None, "--start"),
    end: str | None = typer.Option(None, "--end"),
    all_day: bool = typer.Option(False, "--all-day"),
    notes: str = typer.Option("", "--notes"),
    allow_overlap: bool = typer.Option(False, "--allow-overlap"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Schedule a work session for a task."""
    if all_day and (start or end):
        raise typer.BadParameter("--all-day cannot be combined with --start/--end")
    if not all_day and (start is None or end is None):
        raise typer.BadParameter("provide --start and --end, or use --all-day")
    body = {
        "date": date,
        "start": start,
        "end": end,
        "all_day": all_day,
        "notes": notes,
        "allow_overlap": allow_overlap,
    }
    data = _call("POST", f"/api/tasks/{task_id}/sessions", body=body)
    if as_json:
        _print_json(data)
        return
    typer.echo(f"Scheduled {_short(data['id'])} for {data['title']}")
    _print_block(data)


@app.command()
def rm(ident: str = typer.Argument(...)) -> None:
    """Delete a block or task by id."""
    kind = None
    for candidate in ("blocks", "tasks"):
        response = _request("GET", f"/api/{candidate}/{ident}")
        if response.status_code == 200:
            kind = candidate
            break
    if kind is None:
        typer.secho(f"No block or task with id {ident!r}.", fg="red", err=True)
        raise typer.Exit(1)
    _call("DELETE", f"/api/{kind}/{ident}")
    typer.echo(f"Deleted {kind[:-1]} {_short(ident)}")


@settings_app.callback(invoke_without_command=True)
def settings_show(
    ctx: typer.Context,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show current settings."""
    if ctx.invoked_subcommand is not None:
        return
    _print_settings(_call("GET", "/api/settings"), as_json)


@settings_app.command("set")
def settings_set(
    day_start: str | None = typer.Option(None, "--day-start"),
    day_end: str | None = typer.Option(None, "--day-end"),
    week_starts_on: int | None = typer.Option(None, "--week-starts-on"),
    granularity: int | None = typer.Option(None, "--granularity"),
    buffer: int | None = typer.Option(None, "--buffer"),
    max_range_days: int | None = typer.Option(None, "--max-range-days"),
) -> None:
    """Update one or more settings."""
    body: dict[str, Any] = {}
    if day_start is not None:
        body["day_start"] = day_start
    if day_end is not None:
        body["day_end"] = day_end
    if week_starts_on is not None:
        body["week_starts_on"] = week_starts_on
    if granularity is not None:
        body["granularity_min"] = granularity
    if buffer is not None:
        body["buffer_min"] = buffer
    if max_range_days is not None:
        body["max_range_days"] = max_range_days
    if not body:
        raise typer.BadParameter("provide at least one setting to change")
    _print_settings(_call("PATCH", "/api/settings", body=body), False)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
