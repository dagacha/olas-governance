from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from governance import proposal_monitor as monitor


class ProposalMonitorTests(unittest.TestCase):
    def test_redacted_endpoint_removes_credentials_and_path(self) -> None:
        endpoint = "https://user:password@rpc.example/v2/rpc-secret?api_key=query-secret"

        redacted = monitor.redacted_endpoint(endpoint)

        self.assertEqual(redacted, "https://rpc.example/<redacted>")
        self.assertNotIn("password", redacted)
        self.assertNotIn("rpc-secret", redacted)
        self.assertNotIn("query-secret", redacted)

    def test_abi_fetch_failure_never_echoes_query_credentials(self) -> None:
        error = requests.RequestException("https://api.etherscan.io/api?apikey=etherscan-secret")
        with patch.object(monitor, "get_abi", side_effect=error):
            with self.assertRaises(SystemExit) as raised:
                monitor.fetch_events(1, 2)

        message = str(raised.exception)
        self.assertIn("RequestException", message)
        self.assertNotIn("etherscan-secret", message)
        self.assertNotIn("apikey=", message)

    def test_rpc_failure_never_echoes_endpoint_credentials(self) -> None:
        class FailingWeb3:
            @staticmethod
            def HTTPProvider(*_args: object, **_kwargs: object) -> object:
                return object()

            def __init__(self, _provider: object) -> None:
                raise RuntimeError("https://rpc.example/v2/rpc-secret")

        endpoint = "https://rpc.example/v2/rpc-secret?api_key=query-secret"
        with (
            patch.object(monitor, "rpc_endpoints", return_value=[endpoint]),
            patch.object(monitor, "Web3", FailingWeb3),
        ):
            with self.assertRaises(SystemExit) as raised:
                monitor.latest_block()

        message = str(raised.exception)
        self.assertIn("https://rpc.example/<redacted>", message)
        self.assertNotIn("rpc-secret", message)
        self.assertNotIn("query-secret", message)

    def test_main_writes_outputs_and_uses_actionable_exit_code(self) -> None:
        proposals = [
            {
                "proposal_id": "1",
                "proposer": "0xabc",
                "created_block": 10,
                "vote_start": 20,
                "vote_end": 30,
                "num_targets": 1,
                "targets": "0xdef",
                "description_head": "Test",
                "actionable": True,
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.md"
            csv_path = Path(temp_dir) / "report.csv"
            with (
                patch.object(monitor, "gather", return_value=(["report"], proposals, proposals, 1, 42)),
                patch(
                    "sys.argv",
                    ["proposal_monitor.py", "--out", str(report_path), "--csv", str(csv_path)],
                ),
            ):
                with self.assertRaises(SystemExit) as raised:
                    monitor.main()

            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(report_path.read_text(encoding="utf-8"), "report\n")
            self.assertIn("proposal_id", csv_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
