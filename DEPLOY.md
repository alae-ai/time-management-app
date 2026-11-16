# Deploying with Docker / Dokploy

The image is a multi-stage build: Node builds the React app, then Python serves the API
and the built UI from one container. SQLite lives in the `tm_data` named volume.

Target domain: **https://todo.naoufalelouahabi.com**

## 1. DNS

Create an `A` record (and `AAAA` if you use IPv6) for
`todo.naoufalelouahabi.com` pointing at the Dokploy server.

## 2. Create the Dokploy application

1. Create a **Docker Compose** application and connect this repository. Use the
   Docker Compose type, not Docker Stack, because the compose file builds the image.
2. Set the compose path to `docker-compose.yml`.
3. In **Environment**, add the runtime values you need:

   ```dotenv
   TZ=Africa/Casablanca
   # Optional: only for the in-app chat.
   TM_LLM_BASE_URL=https://api.openai.com/v1
   TM_LLM_API_KEY=sk-...
   TM_LLM_MODEL=gpt-4o-mini
   ```

   `TZ` controls the server's local clock, which this app uses for "today", "now", and
   the free-slot window. Use your real timezone. The LLM values can be left empty.

4. In **Domains**, add:

   | Field | Value |
   |---|---|
   | Host | `todo.naoufalelouahabi.com` |
   | Service | `tm` |
   | Container port | `4317` |
   | HTTPS | enabled (Let's Encrypt) |

5. Deploy. Dokploy injects the Traefik labels and network config. The compose file uses
   `expose`, not a host port, so the container is only reached through Dokploy's proxy.

## 3. Environment variables

The application reads these variables (`tm/config.py`):

| Variable | Purpose | Compose default |
|---|---|---|
| `TM_HOST` | Bind address | `0.0.0.0` |
| `TM_PORT` | Internal HTTP port | `4317` |
| `TM_DATA_DIR` | Data directory | `/app/data` |
| `TM_DB_PATH` | SQLite file | `/app/data/tm.db` |
| `TM_API_URL` | API URL used by the `tm` CLI inside the container | `http://127.0.0.1:4317` |
| `TM_LLM_BASE_URL` | OpenAI-compatible chat base URL | empty |
| `TM_LLM_API_KEY` | Chat API key (keep this secret) | empty |
| `TM_LLM_MODEL` | Chat model name | empty |
| `TZ` | Container timezone (not read by Python config directly) | `UTC` |

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
  JSON with:

  ```bash
  curl https://todo.naoufalelouahabi.com/api/export > backup.json
  ```

- To inspect the DB from the container:

  ```bash
  docker compose exec tm ls -l /app/data
  docker compose exec tm tm state --json
  ```

## Security note

This is a single-user local-first app with **no authentication**. A public domain
exposes both the calendar and its write API. Put Dokploy/Traefik basic auth (or another
access-control middleware) in front of the domain, or keep it on a private network.
