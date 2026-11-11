"""Runtime configuration loaded from the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _resolve_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT / path


DATA_DIR = _resolve_path(os.getenv("TM_DATA_DIR", "data"))
DB_PATH = _resolve_path(os.getenv("TM_DB_PATH", str(DATA_DIR / "tm.db")))

HOST = os.getenv("TM_HOST", "127.0.0.1")
PORT = int(os.getenv("TM_PORT", "4317"))
API_URL = os.getenv("TM_API_URL", f"http://{HOST}:{PORT}")

LLM_BASE_URL = os.getenv("TM_LLM_BASE_URL", "").strip()
LLM_API_KEY = os.getenv("TM_LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("TM_LLM_MODEL", "").strip()


def llm_configured() -> bool:
    return bool(LLM_BASE_URL and LLM_MODEL and LLM_API_KEY)
