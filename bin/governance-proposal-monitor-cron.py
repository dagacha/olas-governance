#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/ubuntu/olas-governance")
UV = Path("/home/ubuntu/.local/bin/uv")
MONITOR = REPO / "governance/proposal_monitor.py"
STATE_DIR = REPO / "state/governance-proposal-monitor"
LOG_DIR = REPO / "logs/governance-proposal-monitor"
ARTIFACT_DIR = REPO / "var/governance-proposal-monitor"
CURSOR_FILE = STATE_DIR / "cursor"
LOCK_FILE = STATE_DIR / "lock"
RUN_LOG = LOG_DIR / "cron.log"
REPORT = ARTIFACT_DIR / "latest.md"
CSV = ARTIFACT_DIR / "latest.csv"
LOOKBACK_BLOCKS = 14400
LOGGER = Path("/usr/bin/logger")
ENV_PATH = REPO / ".env"

sys.path.insert(0, str(REPO))
from governance.telegram_utils import actionable_rows, format_rows_message, read_csv_rows, send_telegram_message


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for path in (STATE_DIR, LOG_DIR, ARTIFACT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def append_log(message: str) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{now()}] {message}\n")


def read_cursor() -> int | None:
    try:
        raw = CURSOR_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    if not raw:
        return None
    return int(raw)


def write_cursor(next_block: int) -> None:
    CURSOR_FILE.write_text(f"{next_block}\n", encoding="utf-8")


def acquire_lock():
    lock_file = LOCK_FILE.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another governance monitor run is already active; exiting.")
        lock_file.close()
        return None
    return lock_file


def run_monitor(cursor: int | None) -> subprocess.CompletedProcess[str]:
    cmd = [str(UV), "run", "python", str(MONITOR)]
    if cursor is None:
        cmd += ["--lookback-blocks", str(LOOKBACK_BLOCKS)]
    else:
        cmd += ["--from-block", str(cursor)]
    cmd += ["--out", str(REPORT), "--csv", str(CSV)]
    return subprocess.run(
        cmd,
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    ensure_dirs()
    lock_file = acquire_lock()
    if lock_file is None:
        return 0

    try:
        cursor = read_cursor()
        append_log(f"starting run cursor={cursor if cursor is not None else 'bootstrap'}")
        result = run_monitor(cursor)
        combined = result.stdout
        if result.stderr:
            combined += "\n[stderr]\n" + result.stderr
        if combined.strip():
            append_log(combined.rstrip())
        else:
            append_log("monitor produced no output")

        match = re.search(r"^scanned_to=(\d+)", result.stdout, re.MULTILINE)
        if not match:
            append_log("missing scanned_to marker; cursor not advanced")
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            return 1 if result.returncode == 0 else result.returncode
        scanned_to = int(match.group(1))
        write_cursor(scanned_to + 1)
        append_log(f"cursor advanced to {scanned_to + 1}")

        if result.returncode == 2:
            actionable = actionable_rows(read_csv_rows(CSV, limit=None))
            if actionable:
                telegram_text = format_rows_message(
                    "GovernorOLAS actionable proposal(s) found:",
                    actionable,
                    footer=f"Report: {REPORT}",
                )
                try:
                    send_telegram_message(telegram_text, env_path=ENV_PATH)
                    append_log(f"telegram alert sent for {len(actionable)} actionable proposal(s)")
                except Exception as exc:  # noqa: BLE001 - Telegram should not break the cron flow
                    append_log(f"telegram send failed: {exc}")
            else:
                append_log("exit 2 but no actionable rows were found in latest.csv")

            subprocess.run(
                [str(LOGGER), "-t", "governance-proposal-monitor", f"actionable proposal(s) found; report={REPORT}"],
                check=False,
            )
        elif result.returncode not in (0, 2):
            append_log(f"monitor failed with exit code {result.returncode}")

        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    finally:
        lock_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
