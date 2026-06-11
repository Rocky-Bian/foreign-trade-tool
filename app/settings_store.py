from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings, settings

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def reload_settings() -> Settings:
    return Settings()


def _upsert_env(key: str, value: str) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    pattern = re.compile(rf"^{re.escape(key)}=")
    replaced = False
    out: list[str] = []
    for line in lines:
        if pattern.match(line):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)

    if not replaced:
        out.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def save_google_keys(api_key: str, cse_id: str) -> None:
    settings.google_api_key = api_key.strip()
    settings.google_cse_id = cse_id.strip()

    if settings.is_vercel:
        return

    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")

    _upsert_env("GOOGLE_API_KEY", api_key.strip())
    _upsert_env("GOOGLE_CSE_ID", cse_id.strip())


def google_configured() -> bool:
    return bool(settings.google_api_key and settings.google_cse_id)
