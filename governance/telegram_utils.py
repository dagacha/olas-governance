"""Telegram helpers for governance alerts and command responses."""

from __future__ import annotations

import csv
import os
import shlex
from pathlib import Path
from typing import Iterable

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
DEFAULT_TIMEOUT = 30
MESSAGE_LIMIT = 3900


def load_env_exports(env_path: Path | str | None) -> None:
    """Load shell-style `export KEY=value` pairs from an env file into os.environ."""
    if env_path is None:
        return
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            continue
        if raw_value.startswith(("'", '"')):
            try:
                value = shlex.split(raw_value, posix=True)[0]
            except Exception:  # noqa: BLE001 - keep parsing permissive for cron .env files
                value = raw_value.strip("\"'")
        else:
            value = raw_value
        os.environ.setdefault(key, value)


def telegram_credentials(env_path: Path | str | None = None) -> tuple[str, str]:
    """Return (token, chat_id), loading them from env or the provided env file."""
    load_env_exports(env_path)
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_TOKEN and CHAT_ID in the environment or .env")
    return token, chat_id


def _message_chunks(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Split long text into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        if current and size + len(line) > limit:
            chunks.append("".join(current).rstrip())
            current = []
            size = 0
        current.append(line)
        size += len(line)
    if current:
        chunks.append("".join(current).rstrip())
    return chunks


def send_telegram_message(
    text: str,
    *,
    token: str | None = None,
    chat_id: str | None = None,
    env_path: Path | str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """Send one or more Telegram messages."""
    if token is None or chat_id is None:
        resolved_token, resolved_chat_id = telegram_credentials(env_path)
        token = token or resolved_token
        chat_id = chat_id or resolved_chat_id

    assert token is not None
    assert chat_id is not None

    for chunk in _message_chunks(text):
        response = requests.post(
            TELEGRAM_API.format(token=token, method="sendMessage"),
            json={
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            payload = {}
        if not response.ok or not payload.get("ok", False):
            raise RuntimeError(f"Telegram sendMessage failed: {response.status_code} {payload!r}")


def read_csv_rows(csv_path: Path | str, limit: int = 2) -> list[dict[str, str]]:
    """Read the last `limit` CSV rows, preserving file order."""
    path = Path(csv_path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-limit:]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _truncate(text: str, limit: int = 180) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def summarize_row(row: dict[str, str]) -> str:
    """Format one CSV row for Telegram."""
    proposal_id = row.get("proposal_id", "?")
    proposer = row.get("proposer", "?")
    vote_start = row.get("vote_start", "?")
    vote_end = row.get("vote_end", "?")
    num_targets = row.get("num_targets", "?")
    actionable = "actionable" if _truthy(row.get("actionable", "")) else "stale"
    description = _truncate(row.get("description_head", "") or "(no description)")
    targets = row.get("targets", "")

    return (
        f"• {proposal_id} [{actionable}]\n"
        f"  proposer: {proposer}\n"
        f"  voteStart: {vote_start} | voteEnd: {vote_end} | targets: {num_targets}\n"
        f"  targets: {targets or '(none)'}\n"
        f"  {description}"
    )


def format_rows_message(title: str, rows: Iterable[dict[str, str]], *, footer: str | None = None) -> str:
    """Create a Telegram-friendly message from CSV rows."""
    parts = [title]
    for row in rows:
        parts.append("")
        parts.append(summarize_row(row))
    if footer:
        parts.append("")
        parts.append(footer)
    return "\n".join(parts)


def actionable_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Filter rows whose `actionable` flag is true."""
    return [row for row in rows if _truthy(row.get("actionable", ""))]
