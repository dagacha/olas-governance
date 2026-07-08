# Olas governance cron deployment

Standalone copy of the governance proposal monitor and Telegram bot.

## Layout

- `bin/governance-proposal-monitor-cron.py` — cron wrapper that scans GovernorOLAS and sends Telegram alerts for actionable proposals
- `bin/governance-telegram-poller.py` — cron wrapper that polls Telegram for `/governance`
- `governance/proposal_monitor.py` — on-chain proposal monitor
- `governance/governance_telegram_bot.py` — Telegram command poller
- `governance/telegram_utils.py` — shared Telegram helpers and CSV formatting
- `.env` — credentials (`ETHERSCAN_API_KEY`, RPC vars, `TELEGRAM_TOKEN`, `CHAT_ID`)
- `pyproject.toml` / `uv.lock` — project metadata for `uv run`

## Installed cron jobs

- Proposal alerts: every 10 minutes
- Telegram command poller: every 1 minute

Check the current entries with:

```bash
crontab -l
```

## Logs and artifacts

- Proposal monitor log: `logs/governance-proposal-monitor/cron.log`
- Telegram poller log: `logs/governance-telegram-bot/telegram-cron.log`
- Latest proposal report: `var/governance-proposal-monitor/latest.md`
- Latest proposal CSV: `var/governance-proposal-monitor/latest.csv`

## Manual runs

From this directory:

```bash
/home/ubuntu/olas-governance/bin/governance-proposal-monitor-cron.py
/home/ubuntu/olas-governance/bin/governance-telegram-poller.py
```

Or invoke the scripts directly with `uv run`:

```bash
cd /home/ubuntu/olas-governance
uv run python ./governance/proposal_monitor.py
uv run python ./governance/governance_telegram_bot.py
```
