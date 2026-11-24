#!/usr/bin/env python3
"""Run one launch-claim check from the command line and print the result.

    python tools/check.py ANNOUNCEMENT_URL EXPLORER_URL CLAIM_TYPE [--text "..."]

CLAIM_TYPE is one of NO_PREMINE, NO_FOUNDER_REWARD, FAIR_LAUNCH,
DECENTRALIZED_MINING, CUSTOM. The contract address comes from --address or
the LCC_ADDRESS environment variable, and defaults to the public deployment
on GenLayer Studio. A signing key can be given in LCC_PRIVATE_KEY; without
one a throwaway key is created for this run (Studio needs no funds).

Exit code: 0 when a check was recorded, 2 when validators agreed that the
check could not be carried out, 3 when no agreement was reached in time.
"""
import argparse
import json
import os
import sys
import time

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet

DEFAULT_ADDRESS = "0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8"
SETTLED = ("ACCEPTED", "FINALIZED")
FAILED = ("UNDETERMINED", "CANCELED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT")


def run_check(address, announcement_url, explorer_url, claim_type, claim_text="", timeout=900, key=None):
    """Returns (status, check_or_None). status is the final transaction status."""
    account = create_account(key) if key else create_account()
    client = create_client(chain=studionet, account=account)
    before = client.read_contract(address=address, function_name="get_count", args=[])
    # Studio refuses transactions without a fee distribution since late Nov 2026 (genlayer-py >= 0.19);
    # the fee deposit needs test GEN, which Studio's faucet gives.
    client.provider.make_request(method="sim_fundAccount", params=[account.address, 10 * 10**18])
    tx = client.write_contract(
        address=address,
        function_name="check_claim",
        args=[announcement_url, explorer_url, claim_type, claim_text],
        fees=client.estimate_transaction_fees(),
    )
    status, started = "PENDING", time.time()
    while time.time() - started < timeout:
        time.sleep(5)
        try:
            # genlayer-py 0.19 dropped status_name from get_transaction; the raw RPC still carries the status
            raw = client.provider.make_request(method="eth_getTransactionByHash", params=[tx]).get("result") or {}
            status = raw.get("status") or status
        except Exception:
            continue
        if status in SETTLED or status in FAILED:
            break
    if status not in SETTLED:
        return status, None
    mine = account.address.lower()
    for check in client.read_contract(address=address, function_name="get_latest", args=[10]):
        if check["submitter"].lower() == mine and int(check["id"]) > before:
            return status, check
    return status, None  # agreed, but nothing recorded (e.g. explorer unreadable)


def main():
    p = argparse.ArgumentParser(description="Run one launch-claim check on GenLayer Studio.")
    p.add_argument("announcement_url")
    p.add_argument("explorer_url")
    p.add_argument("claim_type")
    p.add_argument("--text", default="", help="the claim in the project's words")
    p.add_argument("--address", default=os.environ.get("LCC_ADDRESS", DEFAULT_ADDRESS))
    p.add_argument("--timeout", type=int, default=900)
    a = p.parse_args()
    status, check = run_check(
        a.address, a.announcement_url, a.explorer_url, a.claim_type.upper(), a.text, a.timeout,
        os.environ.get("LCC_PRIVATE_KEY"),
    )
    if check is None:
        print(json.dumps({"status": status, "recorded": False}))
        sys.exit(2 if status in SETTLED else 3)
    print(json.dumps({"status": status, "recorded": True, **check}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
