# Deploying with Docker / Dokploy

The image is a multi-stage build: Node builds the React app, then Python serves the API
and the built UI from one container. SQLite lives in the `tm_data` named volume.

Target domain: **https://calendar.naoufalelouahabi.com**

## 1. DNS

Create an `A` record (and `AAAA` if you use IPv6) for
`calendar.naoufalelouahabi.com` pointing at the Dokploy server.

## 2. Create the Dokploy application

1. Create a **Docker Compose** application and connect this repository. Use the
   Docker Compose type, not Docker Stack, because the compose file builds the image.
2. Set the compose path to `docker-compose.yml`.
3. In **Environment**, add the runtime values you need. The compose file declares these
   names without values, and Dokploy supplies them through its generated `.env`:

   ```dotenv
   TM_HOST=0.0.0.0
   TM_PORT=4317
   TM_DATA_DIR=/app/data
   TM_DB_PATH=/app/data/tm.db
   TM_API_URL=http://127.0.0.1:4317
   TZ=Africa/Casablanca

   # Authentication. Generate the setup token with: openssl rand -hex 24
   TM_SESSION_DAYS=30
   TM_COOKIE_SECURE=1
   TM_SETUP_TOKEN=replace-with-a-random-secret
   TM_PUBLIC_ORIGIN=https://calendar.naoufalelouahabi.com

   # Optional: only for the in-app chat.
   TM_LLM_BASE_URL=https://api.openai.com/v1
   TM_LLM_API_KEY=sk-...
   TM_LLM_MODEL=gpt-4o-mini
   ```

   At minimum set `TM_HOST=0.0.0.0` so Dokploy's proxy can reach the container. The
   other values match the image defaults, but keeping them explicit makes the deployment
   self-documenting. `TZ` controls the server's local clock, which this app uses for
   "today", "now", and the free-slot window. Use your real timezone. The LLM values can
   be left empty.

4. In **Domains**, add:

   | Field | Value |
   |---|---|
   | Host | `calendar.naoufalelouahabi.com` |
   | Service | `tm` |
   | Container port | `4317` |
   | HTTPS | enabled (Let's Encrypt) |

5. Deploy. Dokploy injects the Traefik labels and network config. The compose file uses
   `expose`, not a host port, so the container is only reached through Dokploy's proxy.

6. Open <https://calendar.naoufalelouahabi.com>. On the first run the app shows **Create
   the administrator account**. Enter your email, a password of at least 10 characters,
   and the `TM_SETUP_TOKEN` value. This account becomes the administrator and claims any
   calendar data that existed before authentication was enabled.

7. After the admin account exists, you can remove `TM_SETUP_TOKEN` from Dokploy's
   environment and redeploy. The setup endpoint is disabled once a real account exists.
   Create accounts for other people from **Users** in the top bar.

## 3. Environment variables

The application reads these variables (`tm/config.py`):

| Variable | Purpose | Recommended Dokploy value |
|---|---|---|
| `TM_HOST` | Bind address | `0.0.0.0` |
| `TM_PORT` | Internal HTTP port | `4317` |
| `TM_DATA_DIR` | Data directory | `/app/data` |
| `TM_DB_PATH` | SQLite file | `/app/data/tm.db` |
| `TM_API_URL` | API URL used by the `tm` CLI inside the container | `http://127.0.0.1:4317` |
| `TM_LLM_BASE_URL` | OpenAI-compatible chat base URL | empty |
| `TM_LLM_API_KEY` | Chat API key (keep this secret) | empty |
| `TM_LLM_MODEL` | Chat model name | empty |
| `TM_SESSION_DAYS` | Browser session lifetime in days | `30` |
| `TM_COOKIE_SECURE` | Send the session cookie only over HTTPS | `1` in production |
| `TM_SETUP_TOKEN` | Required on the first-run admin setup screen | random secret |
| `TM_PUBLIC_ORIGIN` | Public origin allowed by CORS | `https://calendar.naoufalelouahabi.com` |
| `TM_API_TOKEN` | Optional token for the `tm` CLI inside the container | create in the UI |
| `TZ` | Container timezone (not read by Python config directly) | e.g. `Africa/Casablanca` |

The compose file uses the short `environment: [NAME]` form. Compose resolves each name
from Dokploy's `.env`, so no values are hardcoded in the repository.

The `TZ` value is set on the container so `datetime.now()` uses the right local time.
Do not put secrets in the Dockerfile; use Dokploy's Environment tab or `.env` for local
Compose runs.

## 4. Local Docker check

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose exec tm tm health
```

The compose file does not publish a host port by default. To open the UI locally,
uncomment the `ports` section in `docker-compose.yml` and use
<http://127.0.0.1:4317>.

## 5. Data and backups

- Database: `/app/data/tm.db` inside the `tm_data` volume.
- The volume survives redeploys. Use Dokploy's named-volume backup feature, or export
  JSON with a personal API token:

  ```bash
  export TM_API_TOKEN="tm_..."
  curl -H "Authorization: Bearer $TM_API_TOKEN" \
    https://calendar.naoufalelouahabi.com/api/export > backup.json
  ```

- To restore an export into the signed-in account:

  ```bash
  curl -H "Authorization: Bearer $TM_API_TOKEN" \
    -H "Content-Type: application/json" \
    -X POST https://calendar.naoufalelouahabi.com/api/import \
    --data-binary @backup.json
  ```

  Add `"replace": true` to the JSON body only when you want to replace that account's
  existing tasks and blocks. Other accounts are never touched.

- To inspect the DB from the container:

  ```bash
  docker compose exec tm ls -l /app/data
  docker compose exec tm tm whoami
  docker compose exec tm tm state --json
  ```

  For the in-container CLI, set `TM_API_TOKEN` in Dokploy's environment (or use
  `docker compose exec -e TM_API_TOKEN=...`).

## Dokploy CLI authentication

The Dokploy CLI v0.30.x tries to write its token to
`/usr/local/lib/node_modules/@dokploy/cli/config.json`. If the global npm package is
root-owned, `dokploy auth` fails with `EACCES: permission denied`.

Use the environment variables supported by the CLI instead of the config file:

```bash
export DOKPLOY_URL="https://dokploy.naoufalelouahabi.com"
export DOKPLOY_AUTH_TOKEN="your-dokploy-api-token"

dokploy overview
```

This avoids writing into `/usr/local/lib/node_modules` entirely.

## Security notes

- Every API route except `/api/health` and the auth/session endpoints requires a login
  cookie or a personal API token.
- Set `TM_COOKIE_SECURE=1` behind HTTPS and keep `TM_SETUP_TOKEN` secret during first-run
  setup. Remove the setup token after the administrator account exists.
- API tokens are shown once. Revoke any token you no longer use from **API tokens** in
  the web UI.
- SQLite is a single file: back up the `tm_data` volume before major upgrades.
