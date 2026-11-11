"""Deterministic free-slot computation."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from tm.dates import (
    ceil_to_grid,
    date_range,
    floor_to_grid,
    fmt_time,
    now_local,
    parse_date,
    parse_time_min,
)
from tm.errors import bad_request
from tm.models import GRANULARITY_CHOICES
from tm.services.settings import get_settings


def _as_minutes(value: str | int, *, end_of_day: bool = False) -> int:
    if isinstance(value, int):
        return value
    return parse_time_min(value, allow_end_of_day=end_of_day)


def find_free_slots(
    conn: sqlite3.Connection,
    from_date: str | date,
    to_date: str | date,
    *,
    min_minutes: int = 30,
    day_start: str | int | None = None,
    day_end: str | int | None = None,
    granularity: int | None = None,
    buffer: int | None = None,
    include_done: bool = False,
    lead_minutes: int = 0,
    now: datetime | None = None,
    max_slots: int = 50,
) -> dict:
    settings = get_settings(conn)
    start_min = (
        _as_minutes(day_start) if day_start is not None else parse_time_min(settings.day_start)
    )
    end_min = (
        _as_minutes(day_end, end_of_day=True)
        if day_end is not None
        else parse_time_min(settings.day_end, allow_end_of_day=True)
    )
    if start_min >= end_min:
        raise bad_request("day_start must be before day_end")

    grid = settings.granularity_min if granularity is None else granularity
    if grid not in GRANULARITY_CHOICES:
        raise bad_request(f"granularity must be one of {sorted(GRANULARITY_CHOICES)}")

    buffer_min = settings.buffer_min if buffer is None else buffer
    if not 0 <= buffer_min <= 120:
        raise bad_request("buffer must be between 0 and 120")
    if not 1 <= min_minutes <= 1440:
        raise bad_request("min_minutes must be between 1 and 1440")
    if not 0 <= lead_minutes <= 1440:
        raise bad_request("lead_minutes must be between 0 and 1440")

    start_date = parse_date(from_date)
    end_date = parse_date(to_date)
    if end_date < start_date:
        raise bad_request("'to' must be on or after 'from'")
    if (end_date - start_date).days + 1 > settings.max_range_days:
        raise bad_request(f"range must be at most {settings.max_range_days} days")

    rows = conn.execute(
        """
        SELECT b.date, b.start_min, b.end_min, b.task_id, t.done AS task_done
        FROM blocks b
        LEFT JOIN tasks t ON t.id = b.task_id
        WHERE b.date BETWEEN ? AND ?
        ORDER BY b.date, COALESCE(b.start_min, -1)
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()

    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    current_dt = now or now_local()
    today = current_dt.date()
    now_minutes = current_dt.hour * 60 + current_dt.minute

    slots: list[dict] = []
    for current in date_range(start_date, end_date):
        if current < today:
            continue

        window_start = start_min
        window_end = end_min
        if current == today:
            window_start = max(
                window_start, ceil_to_grid(now_minutes + lead_minutes, grid)
            )
        if window_start >= window_end:
            continue

        intervals: list[tuple[int, int]] = []
        for row in by_date.get(current.isoformat(), []):
            if not include_done and row["task_id"] and row["task_done"]:
                continue
            if row["start_min"] is None or row["end_min"] is None:
                block_start, block_end = 0, 1440
            else:
                block_start, block_end = row["start_min"], row["end_min"]
            block_start = max(window_start, block_start - buffer_min)
            block_end = min(window_end, block_end + buffer_min)
            if block_start < block_end:
                intervals.append((block_start, block_end))

        intervals.sort()
        merged: list[tuple[int, int]] = []
        for interval_start, interval_end in intervals:
            if merged and interval_start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], interval_end))
            else:
                merged.append((interval_start, interval_end))

        gaps: list[tuple[int, int]] = []
        cursor = window_start
        for interval_start, interval_end in merged:
            if interval_start > cursor:
                gaps.append((cursor, interval_start))
            cursor = max(cursor, interval_end)
        if cursor < window_end:
            gaps.append((cursor, window_end))

        for gap_start, gap_end in gaps:
            if gap_start != window_start:
                gap_start = ceil_to_grid(gap_start, grid)
            if gap_end != window_end:
                gap_end = floor_to_grid(gap_end, grid)
            if gap_end <= gap_start or gap_end - gap_start < min_minutes:
                continue
            all_day = (
                not merged and gap_start == start_min and gap_end == end_min
            )
            slots.append(
                {
                    "date": current.isoformat(),
                    "start": fmt_time(gap_start),
                    "end": fmt_time(gap_end),
                    "minutes": gap_end - gap_start,
                    "all_day": all_day,
                }
            )

    truncated = len(slots) > max_slots
    return {
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
        "window": {"start": fmt_time(start_min), "end": fmt_time(end_min)},
        "min_minutes": min_minutes,
        "slots": slots[:max_slots],
        "truncated": truncated,
    }
