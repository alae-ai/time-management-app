# syntax=docker/dockerfile:1

# Build the React UI.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Runtime: FastAPI serves both /api and the built UI.
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    HOME=/home/app \
    TM_HOST=0.0.0.0 \
    TM_PORT=4317 \
    TM_DATA_DIR=/app/data \
    TM_DB_PATH=/app/data/tm.db \
    TM_API_URL=http://127.0.0.1:4317

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY tm ./tm
RUN pip install --no-cache-dir --no-compile .

COPY --from=web /web/dist ./web/dist

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data \
    && chown -R app:app /app/data

USER app
EXPOSE 4317

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('TM_PORT', '4317') + '/api/health', timeout=4)"

CMD ["tm", "serve"]
