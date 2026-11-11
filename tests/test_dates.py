from __future__ import annotations

from datetime import date

import pytest

from tm.dates import (
    ceil_to_grid,
    date_range,
    floor_to_grid,
    fmt_date,
    fmt_duration,
    fmt_time,
    parse_date,
    parse_time_min,
)


def test_parse_date_accepts_both_formats():
    assert parse_date("2026-12-02") == date(2026, 12, 2)
    assert parse_date("02/12/2026") == date(2026, 12, 2)


@pytest.mark.parametrize("value", ["2026-13-02", "32/12/2026", "tomorrow", ""])
def test_parse_date_rejects_invalid(value):
    with pytest.raises(ValueError):
        parse_date(value)


def test_time_round_trip():
    assert parse_time_min("08:00") == 480
    assert parse_time_min("17:30") == 1050
    assert parse_time_min("24:00", allow_end_of_day=True) == 1440
    assert fmt_time(480) == "08:00"
    assert fmt_time(1440) == "24:00"


@pytest.mark.parametrize("value", ["8:60", "24:00", "-1:00", "noon"])
def test_invalid_times(value):
    with pytest.raises(ValueError):
        parse_time_min(value)


def test_display_helpers():
    assert fmt_date("2026-12-02") == "02/12/2026"
    assert fmt_duration(150) == "2h30"
    assert fmt_duration(180) == "3h"
    assert fmt_duration(45) == "45m"


def test_grid_helpers():
    assert ceil_to_grid(607, 30) == 630
    assert floor_to_grid(607, 30) == 600


def test_date_range_is_inclusive():
    days = list(date_range(date(2026, 12, 1), date(2026, 12, 3)))
    assert len(days) == 3
    assert days[-1] == date(2026, 12, 3)
