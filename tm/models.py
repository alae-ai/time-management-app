"""Pydantic models for the HTTP API and tool layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from tm.dates import fmt_time, parse_date, parse_time_min

GRANULARITY_CHOICES = {5, 10, 15, 20, 30, 60}


class Settings(BaseModel):
    day_start: str = "08:00"
    day_end: str = "22:00"
    week_starts_on: int = 1
    granularity_min: int = 30
    buffer_min: int = 0
    max_range_days: int = 366
    max_chat_messages: int = 40

    @field_validator("day_start", "day_end")
    @classmethod
    def _valid_time(cls, value: str) -> str:
        return fmt_time(parse_time_min(value, allow_end_of_day=True))

    @field_validator("week_starts_on")
    @classmethod
    def _valid_week_start(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("week_starts_on must be 0 (Sunday) or 1 (Monday)")
        return value

    @field_validator("granularity_min")
    @classmethod
    def _valid_granularity(cls, value: int) -> int:
        if value not in GRANULARITY_CHOICES:
            raise ValueError(f"granularity_min must be one of {sorted(GRANULARITY_CHOICES)}")
        return value

    @field_validator("buffer_min")
    @classmethod
    def _valid_buffer(cls, value: int) -> int:
        if not 0 <= value <= 120:
            raise ValueError("buffer_min must be between 0 and 120")
        return value

    @field_validator("max_range_days")
    @classmethod
    def _valid_range(cls, value: int) -> int:
        if not 1 <= value <= 366:
            raise ValueError("max_range_days must be between 1 and 366")
        return value

    @field_validator("max_chat_messages")
    @classmethod
    def _valid_chat_messages(cls, value: int) -> int:
        if not 4 <= value <= 200:
            raise ValueError("max_chat_messages must be between 4 and 200")
        return value

    @model_validator(mode="after")
    def _ordered_window(self) -> Settings:
        start = parse_time_min(self.day_start)
        end = parse_time_min(self.day_end, allow_end_of_day=True)
        if start >= end:
            raise ValueError("day_start must be before day_end")
        return self


class SettingsUpdate(BaseModel):
    day_start: str | None = None
    day_end: str | None = None
    week_starts_on: int | None = None
    granularity_min: int | None = None
    buffer_min: int | None = None
    max_range_days: int | None = None
    max_chat_messages: int | None = None

    @field_validator("day_start", "day_end")
    @classmethod
    def _valid_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value, allow_end_of_day=True))


class TaskCreate(BaseModel):
    title: str
    project: str | None = None
    notes: str = ""
    deadline: str | None = None
    deadline_time: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("deadline")
    @classmethod
    def _deadline(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return parse_date(value).isoformat()

    @field_validator("deadline_time")
    @classmethod
    def _deadline_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value))

    @model_validator(mode="after")
    def _time_needs_date(self) -> TaskCreate:
        if self.deadline_time and not self.deadline:
            raise ValueError("deadline_time requires a deadline date")
        return self


class TaskUpdate(BaseModel):
    title: str | None = None
    project: str | None = None
    notes: str | None = None
    deadline: str | None = None
    deadline_time: str | None = None
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("deadline")
    @classmethod
    def _deadline(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return parse_date(value).isoformat()

    @field_validator("deadline_time")
    @classmethod
    def _deadline_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value))


class BlockCreate(BaseModel):
    title: str
    kind: Literal["appointment", "session"]
    task_id: str | None = None
    date: str
    start: str | None = None
    end: str | None = None
    notes: str = ""
    allow_overlap: bool = False

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("date")
    @classmethod
    def _date(cls, value: str) -> str:
        return parse_date(value).isoformat()

    @field_validator("start")
    @classmethod
    def _start(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value))

    @field_validator("end")
    @classmethod
    def _end(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value, allow_end_of_day=True))

    @model_validator(mode="after")
    def _consistent_block(self) -> BlockCreate:
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be provided together (or both omitted)")
        if self.start is not None and parse_time_min(self.start) >= parse_time_min(
            self.end, allow_end_of_day=True
        ):
            raise ValueError("start must be before end")
        if self.kind == "session" and not self.task_id:
            raise ValueError("a session requires task_id")
        if self.kind == "appointment" and self.task_id:
            raise ValueError("an appointment cannot have task_id")
        return self


class BlockUpdate(BaseModel):
    title: str | None = None
    date: str | None = None
    start: str | None = None
    end: str | None = None
    notes: str | None = None
    allow_overlap: bool = False

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("date")
    @classmethod
    def _date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return parse_date(value).isoformat()

    @field_validator("start")
    @classmethod
    def _start(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value))

    @field_validator("end")
    @classmethod
    def _end(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value, allow_end_of_day=True))


class SessionCreate(BaseModel):
    date: str
    start: str | None = None
    end: str | None = None
    all_day: bool = False
    notes: str = ""
    allow_overlap: bool = False

    @field_validator("date")
    @classmethod
    def _date(cls, value: str) -> str:
        return parse_date(value).isoformat()

    @field_validator("start")
    @classmethod
    def _start(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value))

    @field_validator("end")
    @classmethod
    def _end(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return fmt_time(parse_time_min(value, allow_end_of_day=True))

    @model_validator(mode="after")
    def _consistent_session(self) -> SessionCreate:
        if self.all_day:
            if self.start is not None or self.end is not None:
                raise ValueError("all_day sessions must not include start/end")
            return self
        if self.start is None or self.end is None:
            raise ValueError("a timed session requires start and end")
        if parse_time_min(self.start) >= parse_time_min(self.end, allow_end_of_day=True):
            raise ValueError("start must be before end")
        return self


class TaskOut(BaseModel):
    id: str
    title: str
    project: str | None
    notes: str
    deadline: str | None
    deadline_time: str | None
    done: bool
    done_at: str | None
    created_at: str
    updated_at: str


class BlockOut(BaseModel):
    id: str
    title: str
    kind: Literal["appointment", "session"]
    task_id: str | None
    task_title: str | None = None
    task_project: str | None = None
    date: str
    start: str | None
    end: str | None
    all_day: bool
    notes: str
    created_at: str
    updated_at: str


class Slot(BaseModel):
    date: str
    start: str
    end: str
    minutes: int
    all_day: bool


class FreeSlotsOut(BaseModel):
    from_date: str = Field(serialization_alias="from")
    to_date: str = Field(serialization_alias="to")
    window: dict[str, str]
    min_minutes: int
    slots: list[Slot]
    truncated: bool = False
