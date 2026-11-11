"""Date, time, and display helpers.

Storage is ISO dates (``YYYY-MM-DD``) and minutes from midnight. Inputs accept both
ISO and the European ``DD/MM/YYYY`` form used by the chat and the UI.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from datetime import date, datetime, timedelta

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")

MINUTES_PER_DAY = 24 * 60


def parse_date(value: str | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date {value!r}: use YYYY-MM-DD or DD/MM/YYYY")


def to_iso(value: str | date) -> str:
    return parse_date(value).isoformat()


def fmt_date(value: str | date) -> str:
    """Format as DD/MM/YYYY for humans."""
    return parse_date(value).strftime("%d/%m/%Y")


def parse_time_min(value: str | int, *, allow_end_of_day: bool = False) -> int:
    """Parse ``HH:MM`` (or an int) into minutes from midnight."""
    if isinstance(value, bool):
        raise ValueError(f"invalid time {value!r}")
    if isinstance(value, int):
        minutes = value
    else:
        text = str(value).strip()
        match = _TIME_RE.match(text)
        if not match:
            raise ValueError(f"invalid time {value!r}: use HH:MM")
        hours, mins = int(match.group(1)), int(match.group(2))
        if mins > 59:
            raise ValueError(f"invalid time {value!r}: minutes must be 00-59")
        minutes = hours * 60 + mins

    upper = MINUTES_PER_DAY if allow_end_of_day else MINUTES_PER_DAY - 1
    if not 0 <= minutes <= upper:
        raise ValueError(f"invalid time {value!r}: out of range")
    return minutes


def fmt_time(minutes: int) -> str:
    if minutes == MINUTES_PER_DAY:
        return "24:00"
    if not 0 <= minutes <= MINUTES_PER_DAY:
        raise ValueError(f"invalid minutes {minutes}")
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def fmt_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h{mins:02d}"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def now_local() -> datetime:
    return datetime.now()


def today() -> date:
    return now_local().date()


def now_minutes() -> int:
    current = now_local()
    return current.hour * 60 + current.minute


def now_iso() -> str:
    return now_local().isoformat(timespec="seconds")


def ceil_to_grid(minutes: int, grid: int) -> int:
    return int(math.ceil(minutes / grid) * grid)


def floor_to_grid(minutes: int, grid: int) -> int:
    return int(math.floor(minutes / grid) * grid)
