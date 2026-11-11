# Time Management App — System Design (v0.2)

> Status: M1–M2 implemented (backend, SQLite, free-slot engine, CLI, calendar UI, tests).
> M3 (MCP server + OpenCode workflow) is next. Remaining for M4: LLM base URL/model details.

## 1. Goal

A single-user, local-first time manager:

- Calendar grid with appointments and tasks.
- Tasks (todos) have a checkbox and a deadline; the deadline day is visually highlighted.
- Natural-language planning from two surfaces:
  - this OpenCode chat (LLM = me), and
  - an in-app chat panel backed by an LLM provider.
- Typical flow: "I have a TP deadline on 02/12/2026, give me the free time I have to do that
  project" → the app computes real gaps → the user picks one → the app schedules it.

Non-goals for v1: multi-user, cloud sync, mobile apps, recurring events, notifications,
drag-and-drop rescheduling.

---

## 2. Core architectural decision

**The app's service layer is the single source of truth. Both LLMs are language adapters, not schedulers.**

Neither the OpenCode agent nor the in-app agent may:

- compute free time from memory or from earlier chat context,
- write the database directly,
- invent or "fix" dates/times.

They only call validated tools. The service layer owns persistence, validation, conflict
detection, and the free-slot algorithm. This keeps the calendar UI, both chats, and the
stored data in agreement, and makes free-time results reproducible and testable.

```
                    ┌──────────────────────┐
  OpenCode (me) ───>│ tm CLI / MCP server  │──┐
                    └──────────────────────┘  │
                                              │  HTTP (single writer)
  In-app chat panel ──> /api/chat ──┐         v
  Calendar UI ──────────────────────┴──> FastAPI service layer ──> SQLite (truth)
                    ▲                        │
                    └──── /api/state ────────┘
```

Decision log:

| Area | Decision |
|---|---|
| Backend | Python 3.13 + FastAPI + stdlib `sqlite3` |
| Frontend | React + TypeScript + Vite |
| Storage | SQLite |
| Agent bridges | REST + `tm` CLI **and** an MCP server |
| Chat surfaces | This OpenCode chat **and** an in-app chat panel |
| Free-time window | Editable in Settings; default 08:00–22:00 |
| Week start | Monday |

---

## 3. Data model

Two scheduling tables (a task can have several work sessions; a deadline is not a block),
plus two tables for the in-app chat.

### `tasks` — todos with deadline and checkbox

| column | type | notes |
|---|---|---|
| `id` | TEXT PK | UUID |
| `title` | TEXT NOT NULL | e.g. "TP report" |
| `project` | TEXT NULL | grouping, e.g. "TP", "Project X" |
| `notes` | TEXT NOT NULL DEFAULT '' | |
| `deadline_date` | TEXT NULL | `YYYY-MM-DD`; NULL = backlog |
| `deadline_min` | INTEGER NULL | minutes from midnight; NULL = end of day |
| `done` | INTEGER NOT NULL DEFAULT 0 | checkbox |
| `done_at` | TEXT NULL | |
| `created_at`, `updated_at` | TEXT NOT NULL | ISO timestamps |

### `blocks` — anything that occupies calendar time

| column | type | notes |
|---|---|---|
| `id` | TEXT PK | UUID |
| `title` | TEXT NOT NULL | |
| `kind` | TEXT NOT NULL | `appointment` or `session` |
| `task_id` | TEXT NULL | FK → tasks; required for `session` |
| `date` | TEXT NOT NULL | `YYYY-MM-DD` |
| `start_min` | INTEGER NULL | minutes from midnight |
| `end_min` | INTEGER NULL | both NULL = all-day |
| `notes` | TEXT NOT NULL DEFAULT '' | |
| `created_at`, `updated_at` | TEXT NOT NULL | |

### `conversations` / `messages` — in-app chat history

```sql
CREATE TABLE conversations (
  id         TEXT PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT 'New chat',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE messages (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('system','user','assistant','tool')),
  content         TEXT NOT NULL DEFAULT '',
  meta_json       TEXT,          -- tool_calls, tool_call_id, structured results
  created_at      TEXT NOT NULL
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
```

### `app_settings` — user-editable preferences

Key-value table, validated on write, seeded with defaults on first boot. No secrets here.

```sql
CREATE TABLE app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

Defaults: `dayStart=08:00`, `dayEnd=22:00`, `weekStartsOn=1`, `granularityMin=30`,
`bufferMin=0`, `maxRangeDays=366`, `maxChatMessages=40`.

Validation: `HH:MM` times, `dayStart < dayEnd`, `granularityMin ∈ {5,10,15,20,30,60}`,
`bufferMin ∈ [0,120]`, `weekStartsOn ∈ {0,1}`, `maxRangeDays ∈ [1,366]`.

### Scheduling schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE tasks (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  project       TEXT,
  notes         TEXT NOT NULL DEFAULT '',
  deadline_date TEXT,
  deadline_min  INTEGER,
  done          INTEGER NOT NULL DEFAULT 0,
  done_at       TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  CHECK (deadline_date IS NULL OR deadline_date GLOB
         '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  CHECK (deadline_min IS NULL OR deadline_min BETWEEN 0 AND 1439)
);

CREATE TABLE blocks (
  id         TEXT PRIMARY KEY,
  title      TEXT NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('appointment','session')),
  task_id    TEXT REFERENCES tasks(id) ON DELETE CASCADE,
  date       TEXT NOT NULL,
  start_min  INTEGER,
  end_min    INTEGER,
  notes      TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK ((start_min IS NULL AND end_min IS NULL) OR
         (start_min BETWEEN 0 AND 1439 AND end_min BETWEEN 1 AND 1440
          AND end_min > start_min)),
  CHECK (kind = 'session' OR task_id IS NULL)
);

CREATE INDEX idx_blocks_date ON blocks(date);
CREATE INDEX idx_blocks_task ON blocks(task_id);
CREATE INDEX idx_tasks_deadline ON tasks(deadline_date);
```

Date/time rules:

- Store dates `YYYY-MM-DD`; times as **minutes from midnight** (integers).
- No UTC conversion (single-user wall-clock app). Display/input is `DD/MM/YYYY`, `HH:MM`.
- API, CLI, MCP, and chat tools accept both `DD/MM/YYYY` and `YYYY-MM-DD`, normalize to ISO.
- Cross-midnight blocks are rejected in v1.

---

## 4. Free-slot engine

Pure, deterministic function in `tm/services/free_slots.py`; unit-tested.

Input:

- `from`, `to` (inclusive dates; default `to` = task deadline)
- `min_minutes` (default 30; "3 hours" ⇒ 180)
- `day_start` / `day_end` (from Settings; default 08:00 / 22:00)
- `granularity` (from Settings; default 30 min)
- `buffer_minutes` (from Settings; default 0)
- `lead_minutes` (default 0; today never suggests the past)
- `include_done` (default false)

Omitted parameters are read from `app_settings` at call time; the response echoes the
window actually used, so the UI and both agents display the same numbers.

Per day:

1. Load blocks in range (joined to tasks); drop sessions of done tasks unless `include_done`.
2. All-day block ⇒ `[00:00, 24:00]`.
3. Clip to the day window, expand by buffer, merge overlaps.
4. Complement = gaps.
5. Today: raise window start to `max(day_start, now + lead)`, rounded up.
6. Round gap edges to the granularity grid; drop gaps `< min_minutes`.
7. `all_day: true` when the gap equals the full window with no busy interval.

Response:

```json
{
  "from": "2026-11-11",
  "to": "2026-12-02",
  "window": { "start": "08:00", "end": "22:00" },
  "min_minutes": 180,
  "slots": [
    { "date": "2026-11-30", "start": "17:30", "end": "20:00", "minutes": 150, "all_day": false },
    { "date": "2026-12-01", "start": "08:00", "end": "22:00", "minutes": 840, "all_day": true }
  ]
}
```

Semantics:

- Only blocks occupy time. Deadlines do not reserve time.
- A done task's sessions stop blocking time.
- Chronological order; cap at 50 slots; range capped at 366 days.
- No slot fits ⇒ say so; never silently return a shorter slot.

Write-time conflict check (same transaction as the insert/update):

- Same date and `new.start < old.end && new.end > old.start`; all-day overlaps all.
- `409` with the conflicting blocks; `allow_overlap=true` is an explicit override and the
  agent must ask the user first.

---

## 5. HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{ ok, now, version, llm_configured }` |
| GET | `/api/state?from&to` | tasks + blocks + settings for the calendar |
| GET | `/api/settings` | calendar/scheduling preferences |
| PATCH | `/api/settings` | partial update, validated |
| GET | `/api/tasks?status=open&project=` | list / backlog |
| POST | `/api/tasks` | create |
| PATCH | `/api/tasks/:id` | update, including `done` |
| DELETE | `/api/tasks/:id` | cascade sessions |
| POST | `/api/blocks` | create appointment/session; `409` on overlap |
| PATCH | `/api/blocks/:id` | move/edit; `409` on overlap |
| DELETE | `/api/blocks/:id` | |
| GET | `/api/free-slots` | params from §4 |
| POST | `/api/tasks/:id/sessions` | schedule a session (date + start/end or all-day) |
| GET | `/api/export` | JSON dump |
| POST | `/api/chat` | in-app agent, SSE stream |
| GET | `/api/conversations` | list |
| GET | `/api/conversations/:id/messages` | history |
| DELETE | `/api/conversations/:id` | delete |

Errors: `{ error: { code, message, details? } }`; `400` validation, `404` not found,
`409` conflict, `503` LLM not configured.

---

## 6. Interfaces for agents

### 6.1 `tm` CLI (used by this OpenCode chat)

Python console script in the venv; calls the HTTP API.

```
tm health
tm state    --from 2026-11-11 --to 2026-12-02
tm settings [--json]
tm settings set --day-start 07:00 --day-end 23:00
tm slots    --from 2026-11-11 --to 2026-12-02 --min 180 [--json]
tm tasks    [--open] [--project TP]
tm task add --title "TP report" --deadline 02/12/2026 --project TP
tm task done <id>
tm schedule --task <id> --date 01/12/2026 [--start 17:30 --end 20:00 | --all-day]
tm appointment add --title "Dentist" --date 20/11/2026 --start 09:00 --end 10:00
tm rm <id>
```

`--json` prints a stable machine-readable payload. Human output is compact tables.

### 6.2 MCP server

`python -m tm.mcp_server`, stdio, thin HTTP client over the same API. **No business logic
duplicated.** Tool names (server name `tm`):

```
tm_health
tm_list_schedule(from, to)
tm_get_tasks(status?, project?)
tm_get_settings()
tm_update_settings(day_start?, day_end?, week_starts_on?, granularity_min?, buffer_min?)
tm_create_task(title, deadline?, project?, notes?)
tm_update_task(task_id, ...)
tm_complete_task(task_id, done=true)
tm_delete_task(task_id)
tm_find_free_slots(from, to, min_minutes=30, day_start?, day_end?, include_done=false)
tm_schedule_session(task_id, date, start?, end?, all_day=false, allow_overlap=false)
tm_create_appointment(title, date, start?, end?, notes?)
tm_delete_block(block_id)
```

Project config (`opencode.jsonc`), added during M3:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "tm": {
        "type": "local",
        "command": ["scripts/tm-mcp"],
        "cwd": ".",
        "environment": { "TM_API_URL": "http://127.0.0.1:4317" }
      }
    }
  }
}
```

`scripts/tm-mcp` activates the project venv, so OpenCode does not need a shell profile.

### 6.3 In-app chat

`POST /api/chat` body: `{ conversation_id?, message }`, response: SSE.

Events:

```
event: delta    data: {"text":"..."}
event: tool     data: {"name":"find_free_slots","args":{...}}
event: result   data: {"name":"find_free_slots","result":{...}}
event: done     data: {"message_id":"..."}
event: error    data: {"code":"...","message":"..."}
```

- Server-side agent loop: system prompt (`prompts/agent.md`) + tool schemas, max 8 tool
  rounds, OpenAI-compatible Chat Completions API.
- Config via `.env`: `TM_LLM_BASE_URL`, `TM_LLM_API_KEY`, `TM_LLM_MODEL`
  (works with OpenAI, DeepSeek, Groq, OpenRouter, Ollama, LM Studio). Key stays server-side.
- Missing config ⇒ `503 llm_not_configured`; the calendar still works, the panel shows a
  setup hint. This OpenCode chat keeps working via CLI/MCP regardless.
- History persisted per conversation; context = system prompt + last ~40 messages, tool
  payloads summarized to keep tokens bounded.
- **Proposal/execute split:** free-slot results are returned as structured data and rendered
  as cards. Clicking **Reserve** opens a confirmation modal and calls
  `POST /api/tasks/:id/sessions` directly with the exact slot. The LLM does not need to
  perform the write, which removes a failure mode from the critical path. If the slot is
  not tied to a task, the modal asks for a title and creates an appointment instead.
- Deletes always require a modal confirmation. Writes from plain text (e.g. "create the TP
  task") are allowed; the prompt forbids scheduling without the user naming a slot.

---

## 7. Agent behavior (shared brain, two transports)

`prompts/agent.md` is the single source of rules; `AGENTS.md` points to it and adds CLI
usage for the OpenCode agent.

1. Never compute or recall schedule data. Always fetch.
2. Dates are `DD/MM/YYYY` by default; echo the interpreted date before writing.
3. Free-time requests: call the `slots` tool; `to` defaults to the task deadline, else
   today + 14 days; `min_minutes` defaults to 30, "3 hours" ⇒ 180.
4. Present slots as `DD/MM/YYYY HH:MM–HH:MM (duration)`; full-window gaps say
   "all day free (08:00–22:00)" using the **configured** window. Never auto-pick.
5. After the user picks, write, then re-fetch and confirm.
6. `409` ⇒ report the conflict and propose alternatives. Never force without asking.
7. Date-only pick ⇒ all-day `session` for that task.
8. App not running (`health` fails) ⇒ ask the user to start it; never fabricate data.

---

## 8. UI

**Calendar**

- Month grid, Monday-first; date number, today ring, up to 3 chips + "+N more".
- Deadline day cell highlight when a task is due:
  amber upcoming, stronger orange today, red overdue, grey when all due tasks are done.
- Chips: appointment (blue), session (green, shows project), task due (amber, checkbox).
  Done ⇒ strikethrough + muted.
- Checkbox toggles done optimistically, PATCH, revert on error.
- Click chip → edit popover (title, time, delete). Click empty cell → create menu.
- Right panel: selected day timeline over the configured window (default 08:00–22:00),
  with blocks and visible **free gaps** ("free 17:30–20:00 · 2h30").
- Header: month nav, Today, filters (all / tasks / appointments / done), settings.
- Settings modal: day start/end, week start, granularity, buffer. Saved through
  `PATCH /api/settings`; the grid, day panel, and free-slot engine pick the change up
  immediately (same values come back in `/api/state`).
- Poll `/api/state` every 5 s and on window focus. SSE later if needed.
- Responsive: grid scrolls on narrow screens; day panel drops below.
- Backlog: undated tasks in a collapsible sidebar list with checkboxes.

**Chat panel**

- Toggleable side panel, one active conversation + "New chat", history persisted.
- Streaming assistant text, tool activity line ("checking free time…").
- Free-slot cards: date, time, duration, **Reserve** button + confirmation modal.
- Errors and "LLM not configured" state shown inline.

No drag-and-drop in v1.

---

## 9. Persistence & config

- SQLite `data/tm.db` (WAL, foreign keys on), migrations via `PRAGMA user_version` +
  numbered SQL files.
- Daily `VACUUM INTO 'data/backups/tm-YYYY-MM-DD.db'` (keep 14) on boot and on a timer;
  `GET /api/export` for a portable JSON dump.
- Single writer process: CLI/MCP go through HTTP, chat runs inside FastAPI.
- Bind `127.0.0.1`; no auth; CORS only for the dev origin. `.env` and `data/` gitignored.
- Dev seed script (`python -m tm.seed`).

Runtime preferences live in `app_settings` (no JSON config file). Defaults are inserted on
first boot and edited from the UI or `PATCH /api/settings`. The free-slot engine reads them
per request, and `/api/state` returns them so the calendar renders the same window.

Environment (`.env`):

```
TM_HOST=127.0.0.1
TM_PORT=4317
TM_LLM_BASE_URL=
TM_LLM_API_KEY=
TM_LLM_MODEL=
```

---

## 10. Edge cases & invariants

- Overlap rejected by default; `allow_overlap` only after explicit confirmation.
- All-day block blocks the whole day.
- Done task ⇒ sessions ignored by the free-slot engine but kept on the calendar.
- Deleting a task cascades its sessions (UI confirms).
- Past deadlines allowed, shown red; creating one warns.
- Deadline without time = end of day.
- Free slots never include the past; today starts at now + lead.
- No cross-midnight, no recurrence, no time zones in v1.
- Prompt injection: calendar titles/notes are data; the system prompt says to ignore
  instructions found inside fetched content.
- LLM key is never sent to the browser or written to logs.

---

## 11. Stack & repository layout

Backend: Python 3.13, FastAPI, Uvicorn, Pydantic v2, stdlib `sqlite3`, httpx, Typer,
python-dotenv, `openai` client, `mcp` SDK. Tests: pytest. Lint/format: ruff.

Frontend: React + TypeScript + Vite, plain CSS modules. No heavy calendar dependency.

```
time-management-app/
  DESIGN.md
  AGENTS.md
  README.md
  pyproject.toml
  .env.example
  .gitignore
  prompts/agent.md
  scripts/
    dev.sh
    tm-mcp
  tm/
    api/            # FastAPI routes + SSE
    services/       # tasks, blocks, free_slots, chat, llm, tools
    db.py           # connections, migrations
    models.py       # Pydantic schemas
    dates.py        # parsing/normalization
    cli.py
    mcp_server.py
    config.py
  web/
    src/
      components/   # MonthGrid, DayCell, EventChip, DayPanel, ChatPanel
      api.ts
      App.tsx
  data/             # tm.db, backups/
  tests/
```

Run: `scripts/dev.sh` starts Uvicorn + Vite; production `npm run build` and FastAPI serves
`web/dist`.

---

## 12. Milestones

1. **M1 — Core**: schema/migrations, service layer, free-slot engine + tests, seed, CLI. ✅
2. **M2 — Calendar UI**: month grid, deadline styling, checkbox, day panel with gaps, CRUD,
   settings modal (window, week start, granularity, buffer). ✅
3. **M3 — OpenCode agent**: MCP server, `opencode.jsonc`, shared prompt, end-to-end
   scenarios (create task → slots → schedule → done) through both CLI and MCP.
4. **M4 — In-app chat**: provider client, agent loop, SSE, history persistence, slot cards.
5. **M5 — Polish**: backups/export, filters, README.

M1–M3 deliver the full chat-with-OpenCode flow. M4 adds the standalone chat panel.

---

## 13. Open items

1. **LLM base URL + model** for the in-app chat (OpenAI-compatible) — needed only for M4.
   The API key goes in `.env`; I will not ask for it in chat.
2. In-app chat panel default: visible but disabled with a setup hint until
   `TM_LLM_API_KEY` / `TM_LLM_BASE_URL` / `TM_LLM_MODEL` are set. Assumed unless changed.
3. Nothing else blocks M3.
