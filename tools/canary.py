#!/usr/bin/env python3
"""Weekly canary: run the four fictional examples against the deployed
contract and fail if any verdict differs from the expected one.

The pages are fixed, so a changed verdict means the validators' models or
the network changed how they read them. That is exactly what this watches.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check import DEFAULT_ADDRESS, run_check  # noqa: E402

SITE = "https://checker.brilliantnodes.com/examples"
CASES = [
    ("examplecoin", "mining", "DECENTRALIZED_MINING", "contradicted", "M1_TOP_MINER_ABOVE_HALF"),
    ("examplecoin", "block1", "NO_FOUNDER_REWARD", "contradicted", "P1_EARLY_ALLOCATION_FOUND"),
    ("controlcoin", "block1", "NO_FOUNDER_REWARD", "supported", "P2_EARLY_BLOCKS_SHOWN_CLEAN"),
    ("controlcoin", "mining", "DECENTRALIZED_MINING", "supported", "M2_TOP_MINER_AT_OR_BELOW_THIRD"),
]


def main():
    address = os.environ.get("LCC_ADDRESS", DEFAULT_ADDRESS)
    failures = 0
    for coin, page, claim, want_verdict, want_rule in CASES:
        ann = f"{SITE}/{coin}-announcement.html"
        exp = f"{SITE}/{coin}-explorer-{page}.html"
        got = None
        for attempt in (1, 2):  # one retry: a busy network can time out
            status, check = run_check(address, ann, exp, claim)
            if check is not None:
                got = (check["verdict"], check["rule"])
                break
        ok = got == (want_verdict, want_rule)
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'} {coin:11} {claim:21} want {want_verdict}/{want_rule} got {got} ({status})")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
