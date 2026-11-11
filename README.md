# Time Management App

Local-first calendar and natural-language time planner. The backend, storage, free-slot
engine, settings, CLI, and the calendar UI are implemented (milestones M1–M2). The MCP
server and in-app chat come next.

See [DESIGN.md](DESIGN.md) for the architecture.

## What works today

- SQLite store (`data/tm.db`) with tasks, calendar blocks, settings, and chat tables.
- FastAPI service with validated task/block CRUD and overlap detection.
- Deterministic free-slot engine: merges overlapping blocks, handles all-day blocks,
  done tasks, buffers, granularity, today's lead time, and a configurable day window.
- User-editable settings (window, week start, granularity, buffer) persisted in SQLite.
- React month calendar with deadline-day highlighting, task checkboxes, appointments,
  work sessions, filters, a day panel with live free gaps, and a backlog.
- `tm` CLI for health checks, schedule inspection, task management, scheduling, and
  free-slot queries.
- Test suite covering the slot engine and the HTTP API.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # optional; the defaults work
cd web && npm install && cd ..
```

If you prefer not to activate, prefix commands with `.venv/bin/` (for example
`.venv/bin/tm serve`).

## Run

```bash
scripts/dev.sh
# or, API only / production bundle:
.venv/bin/tm serve
```

`scripts/dev.sh` starts the API and the Vite dev server together. It reuses an API that
is already running on port 4317.

- App (dev): <http://127.0.0.1:5173>
- App (built): <http://127.0.0.1:4317>
- API: <http://127.0.0.1:4317>
- Interactive docs: <http://127.0.0.1:4317/docs>
- Demo data: `.venv/bin/python -m tm.seed` (or `--reset`)

`tm serve` serves the built frontend from `web/dist` when it exists. Rebuild it after
frontend changes:

```bash
cd web && npm run build
```

## CLI

```bash
tm health
tm state --from 11/11/2026 --to 02/12/2026
tm settings
tm settings set --day-start 08:00 --day-end 22:00
tm slots --from 11/11/2026 --to 02/12/2026 --min 180
tm tasks --open
tm task add --title "TP report" --deadline 02/12/2026 --project TP
tm task done <task-id>
tm schedule --task <task-id> --date 01/12/2026 --all-day
tm schedule --task <task-id> --date 30/11/2026 --start 17:30 --end 20:00
tm appointment add --title "Dentist" --date 20/11/2026 --start 09:00 --end 10:00
tm rm <block-or-task-id>
```

Add `--json` to read commands for stable machine-readable output.

The CLI talks to the API over HTTP. The server must be running; `tm health` checks it.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status and whether the LLM is configured |
| GET | `/api/state` | tasks + blocks + settings for a date range |
| GET/POST | `/api/tasks` | list / create tasks |
| GET/PATCH/DELETE | `/api/tasks/{id}` | read / update / delete (cascades sessions) |
| POST | `/api/tasks/{id}/sessions` | schedule a work session |
| POST | `/api/blocks` | create an appointment or session |
| GET/PATCH/DELETE | `/api/blocks/{id}` | read / update / delete |
| GET | `/api/free-slots` | compute free gaps |
| GET/PATCH | `/api/settings` | calendar preferences |
| GET | `/api/export` | portable JSON dump |

Free slots accept `from`, `to`, `min`, and optional `day_start`, `day_end`,
`granularity`, `buffer`, `include_done`.

## Frontend

```bash
cd web
npm install
npm run dev      # http://127.0.0.1:5173, proxies /api to :4317
npm run build    # type-check and write web/dist
```

The UI polls `/api/state` every five seconds and on window focus. Changes made through
the UI use the same REST endpoints as the CLI, so the calendar, CLI, and chat all see
the same data.

## Tests

```bash
.venv/bin/pytest
.venv/bin/ruff check tm tests
cd web && npm run build
```

## Data

- `data/tm.db` (WAL mode, foreign keys on), gitignored.
- Delete the file to start over, or run `python -m tm.seed --reset`.
- Dates are ISO on the wire and `DD/MM/YYYY` in the CLI; times are `HH:MM`.

## Roadmap

- **M3**: MCP server + OpenCode workflow.
- **M4**: in-app chat panel (OpenAI-compatible provider).
- **M5**: backups/export polish.
