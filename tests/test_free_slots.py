from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from tm.errors import AppError
from tm.models import BlockCreate, SessionCreate, SettingsUpdate, TaskCreate
from tm.services.blocks import create_block, create_session
from tm.services.free_slots import find_free_slots
from tm.services.settings import update_settings
from tm.services.tasks import create_task, set_done


def _busy(conn, day: date, start: str, end: str, *, title: str = "busy") -> dict:
    return create_block(
        conn,
        BlockCreate(
            title=title,
            kind="appointment",
            date=day.isoformat(),
            start=start,
            end=end,
        ),
    )


def _slots(conn, day: date, **kwargs):
    now = kwargs.pop("now", datetime.combine(day - timedelta(days=1), time(12, 0)))
    return find_free_slots(conn, day, day, now=now, **kwargs)


def test_empty_day_is_all_day(conn, future_day):
    result = _slots(conn, future_day)
    assert result["slots"] == [
        {
            "date": future_day.isoformat(),
            "start": "08:00",
            "end": "22:00",
            "minutes": 840,
            "all_day": True,
        }
    ]
    assert result["window"] == {"start": "08:00", "end": "22:00"}


def test_busy_block_splits_the_day(conn, future_day):
    _busy(conn, future_day, "10:00", "12:00")
    slots = _slots(conn, future_day)["slots"]
    assert [(s["start"], s["end"], s["minutes"]) for s in slots] == [
        ("08:00", "10:00", 120),
        ("12:00", "22:00", 600),
    ]
    assert all(not s["all_day"] for s in slots)


def test_min_duration_filter(conn, future_day):
    _busy(conn, future_day, "10:00", "12:00")
    slots = _slots(conn, future_day, min_minutes=180)["slots"]
    assert [(s["start"], s["end"]) for s in slots] == [("12:00", "22:00")]


def test_overlapping_blocks_are_merged(conn, future_day):
    _busy(conn, future_day, "10:00", "12:00")
    create_block(
        conn,
        BlockCreate(
            title="overlap",
            kind="appointment",
            date=future_day.isoformat(),
            start="11:00",
            end="13:00",
            allow_overlap=True,
        ),
    )
    slots = _slots(conn, future_day)["slots"]
    assert [(s["start"], s["end"]) for s in slots] == [
        ("08:00", "10:00"),
        ("13:00", "22:00"),
    ]


def test_all_day_block_leaves_no_slot(conn, future_day):
    create_block(
        conn,
        BlockCreate(
            title="Conference",
            kind="appointment",
            date=future_day.isoformat(),
            start=None,
            end=None,
        ),
    )
    assert _slots(conn, future_day)["slots"] == []


def test_done_task_sessions_are_ignored(conn, future_day):
    task = create_task(
        conn,
        TaskCreate(title="TP report", deadline=future_day.isoformat()),
    )
    create_session(
        conn,
        task["id"],
        SessionCreate(
            date=future_day.isoformat(), start="10:00", end="12:00"
        ),
    )
    assert len(_slots(conn, future_day)["slots"]) == 2

    set_done(conn, task["id"])
    slots = _slots(conn, future_day)["slots"]
    assert len(slots) == 1
    assert slots[0]["all_day"] is True

    with_done = _slots(conn, future_day, include_done=True)["slots"]
    assert len(with_done) == 2


def test_settings_control_the_window(conn, future_day):
    update_settings(conn, SettingsUpdate(day_start="09:00", day_end="18:00"))
    result = _slots(conn, future_day)
    assert result["window"] == {"start": "09:00", "end": "18:00"}
    assert result["slots"][0]["start"] == "09:00"
    assert result["slots"][0]["end"] == "18:00"
    assert result["slots"][0]["minutes"] == 540


def test_window_override(conn, future_day):
    result = _slots(conn, future_day, day_start="07:00", day_end="23:00")
    assert result["slots"][0]["start"] == "07:00"
    assert result["slots"][0]["end"] == "23:00"


def test_buffer_rounds_gaps_to_the_grid(conn, future_day):
    _busy(conn, future_day, "10:00", "12:00")
    slots = _slots(conn, future_day, buffer=15)["slots"]
    assert [(s["start"], s["end"], s["minutes"]) for s in slots] == [
        ("08:00", "09:30", 90),
        ("12:30", "22:00", 570),
    ]


def test_granularity_rounds_internal_edges(conn, future_day):
    _busy(conn, future_day, "10:07", "11:07")
    slots = _slots(conn, future_day)["slots"]
    assert [(s["start"], s["end"], s["minutes"]) for s in slots] == [
        ("08:00", "10:00", 120),
        ("11:30", "22:00", 630),
    ]


def test_today_starts_at_now(conn, future_day):
    now = datetime.combine(future_day, time(12, 7))
    slots = _slots(conn, future_day, now=now)["slots"]
    assert [(s["start"], s["end"], s["minutes"]) for s in slots] == [
        ("12:30", "22:00", 570)
    ]
    assert slots[0]["all_day"] is False


def test_past_days_are_skipped(conn, future_day):
    now = datetime.combine(future_day + timedelta(days=1), time(9, 0))
    result = find_free_slots(
        conn,
        future_day - timedelta(days=1),
        future_day,
        now=now,
    )
    assert result["slots"] == []


def test_range_is_capped(conn, future_day):
    with pytest.raises(AppError) as error:
        find_free_slots(
            conn,
            future_day,
            future_day + timedelta(days=400),
            now=datetime.combine(future_day - timedelta(days=1), time(12, 0)),
        )
    assert error.value.status_code == 400


def test_truncated_flag(conn, future_day):
    result = find_free_slots(
        conn,
        future_day,
        future_day + timedelta(days=60),
        now=datetime.combine(future_day - timedelta(days=1), time(12, 0)),
        max_slots=10,
    )
    assert len(result["slots"]) == 10
    assert result["truncated"] is True
