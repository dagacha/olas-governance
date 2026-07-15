# Olas Governance

Cron-oriented monitoring and Telegram alerts for proposals on the Olas DAO's
Ethereum `GovernorOLAS` contract. It is an operational tool: it reads public
chain data, writes local reports/state, and can send alerts to one authorized
Telegram chat. It does not submit transactions or cast votes.

## Requirements

- Python 3.10–3.13
- [uv](https://docs.astral.sh/uv/)
- An Etherscan API key
- A Telegram bot token and authorized chat ID for alerts/commands
- An authenticated Ethereum RPC endpoint is recommended

## Install

```bash
git clone https://github.com/dagacha/olas-governance.git
cd olas-governance
uv sync --all-groups
cp .env.example .env
chmod 600 .env
```

Edit `.env` with real credentials. It is ignored by Git; never commit it. See
[SECURITY.md](SECURITY.md) for credential handling and rotation requirements.

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `ETHERSCAN_API_KEY` | Yes | Fetches the deployed GovernorOLAS ABI. |
| `ALCHEMY_API_KEY` | Recommended | Builds an authenticated Ethereum mainnet RPC URL. |
| `ETH_RPC` or `ETH_RPC_URL` | Recommended | Alternative authenticated Ethereum RPC URL. |
| `TELEGRAM_TOKEN` | For alerts/commands | Telegram bot credential. |
| `CHAT_ID` | For alerts/commands | Only this Telegram chat may use `/governance`. |

If no RPC variable is configured, the monitor tries public endpoints. They may
rate-limit or be unavailable; use an authenticated endpoint for reliable cron
operation.

## Run

Show the monitor options:

```bash
uv run python governance/proposal_monitor.py --help
```

Run a scan and write local report artifacts:

```bash
uv run python governance/proposal_monitor.py \
  --lookback-blocks 14400 \
  --out var/governance-proposal-monitor/latest.md \
  --csv var/governance-proposal-monitor/latest.csv
```

The monitor exits `0` when no actionable proposal is found, `2` when at least
one proposal remains in its voting-delay review window, and a non-zero,
non-`2` code for errors.

The Telegram poller responds to `/governance` only in `CHAT_ID`:

```bash
uv run python governance/governance_telegram_bot.py
```

## Cron deployment

The wrappers resolve the repository directory from their own location; the
clone may live anywhere. Ensure `uv` is available to cron's `PATH`. If it is
not, set `UV_BIN` in the crontab environment (it is not read from `.env`):

```cron
PATH=/usr/local/bin:/usr/bin:/bin
UV_BIN=/home/deploy/.local/bin/uv
0 9 * * * cd /srv/olas-governance && /usr/bin/env python3 bin/governance-proposal-monitor-cron.py
* * * * * cd /srv/olas-governance && /usr/bin/env python3 bin/governance-telegram-poller.py
```

Local operational data is intentionally untracked:

- logs: `logs/`
- cursor and poll offsets: `state/`
- latest reports and CSV output: `var/`

## Development

```bash
uv lock --check
uv run ruff check .
uv run python -m unittest discover -s tests -v
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. For
support use [SUPPORT.md](SUPPORT.md); report vulnerabilities privately under
[SECURITY.md](SECURITY.md).

## Public release

Before changing repository visibility, complete and record the
[public release checklist](RELEASING.md).

## License

Licensed under the [Apache License 2.0](LICENSE). Copyright notices in source
files and [NOTICE](NOTICE) identify applicable ownership.
