"""Long-poll Telegram for `/governance` and reply with recent proposals."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from governance.telegram_utils import (
    TELEGRAM_API,
    format_rows_message,
    read_csv_rows,
    redact_telegram_error,
    send_telegram_message,
    telegram_credentials,
)

ENV_PATH = REPO / ".env"
CSV_PATH = REPO / "var/governance-proposal-monitor/latest.csv"
STATE_DIR = REPO / "state/governance-telegram-bot"
OFFSET_FILE = STATE_DIR / "offset"
POLL_TIMEOUT = 0
HTTP_TIMEOUT = 30
COMMAND_RE = re.compile(r"^/governance(?:@\w+)?(?:\s|$)", re.IGNORECASE)


def load_offset() -> int:
    try:
        return int(OFFSET_FILE.read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return 0
    except ValueError:
        return 0


def save_offset(offset: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(f"{offset}\n", encoding="utf-8")


def get_updates(token: str, offset: int) -> list[dict]:
    response = requests.get(
        TELEGRAM_API.format(token=token, method="getUpdates"),
        params={
            "timeout": POLL_TIMEOUT,
            "offset": offset,
            "allowed_updates": json.dumps(["message", "channel_post"]),
        },
        timeout=HTTP_TIMEOUT,
    )
    payload = response.json()
    if not response.ok or not payload.get("ok", False):
        raise RuntimeError(f"Telegram getUpdates failed: {response.status_code} {payload!r}")
    updates = payload.get("result", [])
    return updates if isinstance(updates, list) else []


def extract_update_message(update: dict) -> dict | None:
    return update.get("message") or update.get("channel_post")


def chat_matches(message: dict, chat_id: str) -> bool:
    chat = message.get("chat") or {}
    return str(chat.get("id")) == str(chat_id)


def command_text(message: dict) -> str:
    return (message.get("text") or message.get("caption") or "").strip()


def governance_response() -> str:
    rows = read_csv_rows(CSV_PATH, limit=2)
    if not rows:
        return f"No governance proposals captured yet.\nSource: {CSV_PATH}"
    return format_rows_message(
        "Last 2 governance proposals:",
        rows,
        footer=f"Source: {CSV_PATH}",
    )


def main() -> int:
    token, chat_id = telegram_credentials(ENV_PATH)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    offset = load_offset()
    print(f"Telegram governance bot poller started; chat_id={chat_id}; offset={offset}")

    try:
        updates = get_updates(token, offset)
        for update in updates:
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            try:
                message = extract_update_message(update)
                if not message or not chat_matches(message, chat_id):
                    continue
                text = command_text(message)
                if not COMMAND_RE.match(text):
                    continue
                reply = governance_response()
                send_telegram_message(reply, token=token, chat_id=chat_id, env_path=ENV_PATH)
                print(f"Handled /governance at update_id={update.get('update_id')}")
            finally:
                save_offset(offset)
    except Exception as exc:  # noqa: BLE001 - keep the poller quiet on transient API/network errors
        print(f"Telegram bot error: {redact_telegram_error(exc)}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
