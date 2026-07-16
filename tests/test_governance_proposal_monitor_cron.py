from __future__ import annotations

import importlib.util
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "governance_proposal_monitor_cron", ROOT / "bin/governance-proposal-monitor-cron.py"
)
assert SPEC and SPEC.loader
cron = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cron)


class GovernanceProposalMonitorCronTests(unittest.TestCase):
    def test_failed_monitor_with_marker_does_not_advance_cursor(self) -> None:
        result = subprocess.CompletedProcess(
            args=["monitor"], returncode=1, stdout="scanned_to=123\n", stderr="write failed\n"
        )
        write_cursor = Mock()

        with (
            patch.object(cron, "ensure_dirs"),
            patch.object(cron, "acquire_lock", return_value=io.StringIO()),
            patch.object(cron, "read_cursor", return_value=100),
            patch.object(cron, "run_monitor", return_value=result),
            patch.object(cron, "append_log"),
            patch.object(cron, "write_cursor", write_cursor),
        ):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return_code = cron.main()

        self.assertEqual(return_code, 1)
        write_cursor.assert_not_called()

    def test_actionable_telegram_failure_does_not_advance_cursor(self) -> None:
        result = subprocess.CompletedProcess(args=["monitor"], returncode=2, stdout="scanned_to=123\n", stderr="")
        write_cursor = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "latest.md"
            csv = Path(temp_dir) / "latest.csv"
            report.touch()
            csv.touch()
            with (
                patch.object(cron, "REPORT", report),
                patch.object(cron, "CSV", csv),
                patch.object(cron, "LOGGER", None),
                patch.object(cron, "ensure_dirs"),
                patch.object(cron, "acquire_lock", return_value=io.StringIO()),
                patch.object(cron, "read_cursor", return_value=100),
                patch.object(cron, "run_monitor", return_value=result),
                patch.object(cron, "append_log") as append_log,
                patch.object(cron, "write_cursor", write_cursor),
                patch.object(cron, "read_csv_rows", return_value=[]),
                patch.object(cron, "actionable_rows", return_value=[{}]),
                patch.object(cron, "format_rows_message", return_value="alert"),
                patch.object(
                    cron,
                    "send_telegram_message",
                    side_effect=RuntimeError("https://api.telegram.org/bot123:token/sendMessage"),
                ),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    return_code = cron.main()

        self.assertEqual(return_code, 1)
        write_cursor.assert_not_called()
        self.assertIn("<redacted>", append_log.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
