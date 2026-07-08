#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/ubuntu/olas-governance")
UV = Path("/home/ubuntu/.local/bin/uv")
SCRIPT = REPO / "governance/governance_telegram_bot.py"
LOG_DIR = REPO / "logs/governance-telegram-bot"
RUN_LOG = LOG_DIR / "telegram-cron.log"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def append_log(message: str) -> None:
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{now()}] {message}\n")


def main() -> int:
    ensure_dirs()
    append_log("starting Telegram poller run")
    result = subprocess.run(
        [str(UV), "run", "python", str(SCRIPT)],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    combined = result.stdout
    if result.stderr:
        combined += "\n[stderr]\n" + result.stderr
    if combined.strip():
        append_log(combined.rstrip())
    else:
        append_log("Telegram poller produced no output")
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
