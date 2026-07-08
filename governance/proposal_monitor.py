#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Monitor the live GovernorOLAS for newly created proposals.

Surfaces every new `ProposalCreated` event on the main GovernorOLAS so a watcher can
review a proposal *during* its `votingDelay` window (AIP-8 "Layer 1": voting power is
snapshotted at `propose + votingDelay`, so the community only defends effectively if it
notices a bad proposal before that snapshot). This is the reactive-capacity trigger the
brake depends on — the brake buys time, but only if someone is watching.

Designed to be run from a cron. It is **stateless**: each run scans a block window and
reports the proposals created within it. Track "already alerted" externally by advancing
the window — pass `--from-block <last_scanned+1>` (and persist the printed `scanned_to`
block for the next run), or use `--lookback-blocks N` to re-scan the last N blocks each
run (pick N comfortably larger than the cron interval so no block is skipped).

Exit code is 2 when at least one new proposal is found (0 otherwise, non-2 on error), so
a cron wrapper can gate a notification on `$? -eq 2` without parsing stdout.

Env: ETHERSCAN_API_KEY (contract ABI). RPC for reads: ALCHEMY_API_KEY -> ETH_RPC /
ETH_RPC_URL -> public fallback (a free-tier RPC is fine).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")

GOVERNOR_ADDRESS = "0x060D0CBdDFb0498d610E2EF55C01516B5B1251E6"  # current GovernorOLAS (mainnet); retired: 0x34C8...dd5 (genesis), 0x8e84...b401 (v2)
SECONDS_PER_BLOCK = 12  # mainnet ~12s/block, for converting the votingDelay window to a wall-clock deadline

# Default re-scan window: ~2 days of blocks. Comfortably larger than any hourly cron
# interval, so a single missed/late run never drops a proposal. Override with
# --lookback-blocks or pin an explicit --from-block.
DEFAULT_LOOKBACK_BLOCKS = 14400

# eth_getLogs chunk size. Start large (fast on Alchemy and endpoints like BlockPI that
# allow 5000); fetch_events auto-halves per endpoint down to MIN_LOG_SPAN when a provider
# rejects the span (public tiers cap anywhere from 5000 down to ~50 blocks).
MAX_LOG_SPAN = 5000
MIN_LOG_SPAN = 50

PUBLIC_RPCS = ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com", "https://cloudflare-eth.com"]


def _is_range_error(exc):
    """True if an RPC error looks like an eth_getLogs block-range limit (vs. a real fault)."""
    msg = str(exc).lower()
    return "range" in msg or "limited to" in msg or "too large" in msg or "-32005" in msg


def get_abi(address):
    url = (
        f"https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getabi"
        f"&address={address}&apikey={ETHERSCAN_API_KEY}"
    )
    data = requests.get(url, timeout=30).json()
    if data["status"] == "1":
        return json.loads(data["result"])
    raise ValueError(f"Etherscan getabi failed for {address}: {data.get('result')}")


def rpc_endpoints():
    """Ordered RPC candidate list: Alchemy -> ETH_RPC / ETH_RPC_URL -> public fallbacks.

    Returns them all (not just the first) so callers can fail over per request — public
    endpoints frequently 403/rate-limit mid-scan, and a cron shouldn't die on one flaky host.
    """
    endpoints = []
    if ALCHEMY_API_KEY:
        endpoints.append(f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}")
    # Accept either ETH_RPC or the repo's forge-style ETH_RPC_URL name.
    explicit_rpc = os.getenv("ETH_RPC") or os.getenv("ETH_RPC_URL")
    if explicit_rpc:
        endpoints.append(explicit_rpc)
    endpoints += PUBLIC_RPCS
    return endpoints


def fetch_events(from_block, to_block):
    """Return ProposalCreated events in [from_block, to_block], chunked under the log-span cap.

    Tries each RPC endpoint in turn; on any failure it advances to the next endpoint and
    restarts the scan. Raises SystemExit only if every endpoint fails.
    """
    try:
        governor_abi = get_abi(GOVERNOR_ADDRESS)
    except Exception as exc:  # noqa: BLE001 - surface ABI fetch failures before RPC retries
        raise SystemExit(f"Failed to fetch Governor ABI from Etherscan for {GOVERNOR_ADDRESS}: {exc}") from exc

    endpoints = rpc_endpoints()
    last_error = None
    for rpc in endpoints:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
            gov = w3.eth.contract(address=Web3.to_checksum_address(GOVERNOR_ADDRESS), abi=governor_abi)
            events = []
            start = from_block
            span = MAX_LOG_SPAN
            while start <= to_block:
                end = min(start + span - 1, to_block)
                try:
                    events += gov.events.ProposalCreated().get_logs(fromBlock=start, toBlock=end)
                    start = end + 1
                except Exception as exc:  # noqa: BLE001
                    # Endpoint rejected this span (per-request block-range cap). Halve and
                    # retry the same chunk on this endpoint before giving up on it.
                    if span > MIN_LOG_SPAN and _is_range_error(exc):
                        span = max(MIN_LOG_SPAN, span // 2)
                        continue
                    raise
            return events
        except Exception as exc:  # noqa: BLE001 - any RPC/decode error -> try the next endpoint
            last_error = f"{type(exc).__name__} on {rpc}: {exc}"
    raise SystemExit(
        f"All RPC endpoints failed. Last error: {last_error}\nSet ALCHEMY_API_KEY, ETH_RPC, or ETH_RPC_URL."
    )


def latest_block():
    """Current head block, trying each RPC endpoint in turn."""
    last_error = None
    for rpc in rpc_endpoints():
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
            return w3.eth.block_number
        except Exception as exc:  # noqa: BLE001 - any RPC error -> try the next endpoint
            last_error = f"{type(exc).__name__} on {rpc}: {exc}"
    raise SystemExit(
        f"All RPC endpoints failed. Last error: {last_error}\nSet ALCHEMY_API_KEY, ETH_RPC, or ETH_RPC_URL."
    )


def gather(from_block=None, lookback_blocks=DEFAULT_LOOKBACK_BLOCKS):
    """Scan a block window for new proposals.

    Returns (lines, proposals, actionable_proposals, scanned_from, scanned_to). `proposals`
    is every decoded ProposalCreated event in the window; `actionable_proposals` is the
    subset still before their `voteStart` snapshot — the only ones worth alerting on, since
    a proposal past its snapshot can no longer be countered by locking OLAS.
    """
    latest = latest_block()
    if from_block is None:
        from_block = max(0, latest - lookback_blocks)
    from_block = min(from_block, latest)

    events = fetch_events(from_block, latest)
    events.sort(key=lambda e: (e["blockNumber"], e["logIndex"]))

    lines = [
        "====== GovernorOLAS proposal monitor ======",
        f"Governor:    {GOVERNOR_ADDRESS}",
        f"Scanned:     blocks {from_block:,} -> {latest:,} (latest)",
    ]
    header_count_idx = len(lines)  # filled in below once actionable proposals are counted
    lines.append("")

    proposals = []
    for e in events:
        a = e["args"]
        proposal_id = a["proposalId"]
        proposer = a["proposer"]
        targets = a["targets"]
        # OZ ProposalCreated uses voteStart/voteEnd (block numbers on the deployed lineage).
        vote_start = a.get("voteStart", a.get("startBlock"))
        vote_end = a.get("voteEnd", a.get("endBlock"))
        description = a.get("description", "")
        block = e["blockNumber"]

        # votingDelay window closes at vote_start: the review deadline before the snapshot locks.
        # Only proposals still before their snapshot are "actionable" — once voteStart has
        # passed, locking OLAS no longer changes the vote, so re-alerting on them is noise.
        blocks_to_start = vote_start - latest
        actionable = blocks_to_start > 0
        if actionable:
            eta = datetime.now(timezone.utc).timestamp() + blocks_to_start * SECONDS_PER_BLOCK
            snapshot_note = (
                f"~{blocks_to_start * SECONDS_PER_BLOCK / 86400:.2f} d "
                f"(voteStart {vote_start:,}, ~{datetime.fromtimestamp(eta, timezone.utc):%Y-%m-%d %H:%M UTC})"
            )
        else:
            snapshot_note = f"PASSED (voteStart {vote_start:,} already reached — snapshot locked)"

        first_line = description.strip().splitlines()[0] if description.strip() else "(no description)"
        if len(first_line) > 200:
            first_line = first_line[:197] + "..."

        proposals.append(
            {
                "proposal_id": str(proposal_id),
                "proposer": proposer,
                "created_block": block,
                "vote_start": vote_start,
                "vote_end": vote_end,
                "num_targets": len(targets),
                "targets": ";".join(targets),
                "description_head": first_line,
                "actionable": actionable,
            }
        )

        status = "ACTIONABLE (in review window)" if actionable else "stale (snapshot locked)"
        lines += [
            "",
            f"--- Proposal {proposal_id} [{status}] ---",
            f"Proposer:       {proposer}",
            f"Created block:  {block:,}",
            f"Vote start:     block {vote_start:,}  | review window closes in {snapshot_note}",
            f"Vote end:       block {vote_end:,}",
            f"Targets ({len(targets)}):    {', '.join(targets) if targets else '(none)'}",
            f"Description:    {first_line}",
        ]

    actionable_proposals = [p for p in proposals if p["actionable"]]
    stale_count = len(proposals) - len(actionable_proposals)
    lines[header_count_idx] = (
        f"Proposals in window: {len(proposals)} "
        f"({len(actionable_proposals)} actionable, {stale_count} stale/snapshot-locked)"
    )

    if not actionable_proposals:
        lines.append("")
        lines.append("No proposals in their votingDelay review window. Nothing to alert on.")

    return lines, proposals, actionable_proposals, from_block, latest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-block",
        type=int,
        default=None,
        metavar="N",
        help="scan from this block (inclusive). Persist the printed scanned_to+1 for the next run. "
        "Overrides --lookback-blocks.",
    )
    parser.add_argument(
        "--lookback-blocks",
        type=int,
        default=DEFAULT_LOOKBACK_BLOCKS,
        metavar="N",
        help=f"if --from-block is unset, scan the last N blocks (default {DEFAULT_LOOKBACK_BLOCKS}, ~2 d).",
    )
    parser.add_argument("--out", metavar="PATH", help="also write the text report to PATH")
    parser.add_argument("--csv", metavar="PATH", help="write the proposals table to PATH as CSV")
    args = parser.parse_args()

    lines, proposals, actionable_proposals, _scanned_from, scanned_to = gather(
        from_block=args.from_block, lookback_blocks=args.lookback_blocks
    )
    report = "\n".join(lines)
    print(report)
    print(f"\nscanned_to={scanned_to}  (pass --from-block {scanned_to + 1} next run)")

    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
        print(f"Wrote report to {args.out}")

    if args.csv:
        import csv as _csv

        fields = [
            "proposal_id",
            "proposer",
            "created_block",
            "vote_start",
            "vote_end",
            "num_targets",
            "targets",
            "description_head",
            "actionable",
        ]
        with open(args.csv, "w", newline="") as f:
            writer = _csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(proposals)
        print(f"Wrote {len(proposals)} proposals to {args.csv}")

    # Exit 2 signals "actionable proposal(s) found" — i.e. still inside their votingDelay
    # review window — so a cron wrapper only notifies while a lock/vote response can still
    # matter. Stale (snapshot-locked) proposals are reported but never trigger the alert.
    sys.exit(2 if actionable_proposals else 0)


if __name__ == "__main__":
    main()
