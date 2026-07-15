# Contributing

Thanks for improving Olas Governance.

## Before opening a pull request

1. Create a branch from `main`.
2. Keep each pull request focused and explain its operational impact.
3. Do not commit credentials, `.env`, generated logs, state, or proposal reports.
4. Add or update deterministic tests for behavior changes.

## Local checks

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --all-groups
uv lock --check
uv run ruff check .
uv run python -m unittest discover -s tests -v
```

Run the monitor interface without contacting the network:

```bash
uv run python governance/proposal_monitor.py --help
```

## Pull requests

- Describe the problem, approach, validation performed, and configuration changes.
- Keep secrets out of command output, exceptions, fixtures, and screenshots.
- Preserve fail-closed behavior around the Telegram and RPC configuration.
- A maintainer review and passing CI are required before merge.

## Reporting vulnerabilities

Do not open a public issue for a suspected vulnerability. Follow [SECURITY.md](SECURITY.md).
