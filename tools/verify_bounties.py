#!/usr/bin/env python3
"""Check a Studio live-run record of LaunchClaimBounties against the chain. Reads only.

    python tools/verify_bounties.py [examples/live/bounties-studio.json]

1. The code deployed by the recorded deployment transaction is, byte for
   byte, contracts/launch_claim_bounties.py in this repository.
2. Every recorded transaction exists on Studio, went to the recorded
   contract from the recorded sender, and has the recorded consensus result,
   execution result, return value and creation time.
3. Every filing's digest is the sha256 the record says it is: for a filing
   that was judged, the rule, block and salt revealed in the judgement give
   the digest that was filed.
4. Each bounty, read from the contract now, is in the recorded final state
   with the recorded winner and agreed facts.
5. The contract's balance equals locked + credited + burned.

A throwaway key is made for the reads; nothing is signed or sent. Exit code 1 on any mismatch.
"""
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import balance, client, read, seal, summary, tx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "live" / "bounties-studio.json"
    rec = json.loads(path.read_text())
    c, _acct = client()
    addr, bad = rec["address"], []

    # 1. deployed code
    d = tx(c, rec["deploy"]["tx"])
    code = base64.b64decode(((d.get("data") or {}).get("contract_code")) or "")
    source = (ROOT / rec["contract_source"]).read_bytes()
    if code != source:
        bad.append(f"deployed code differs from {rec['contract_source']} ({len(code)} bytes on chain, {len(source)} in the repository)")
    if hashlib.sha256(code).hexdigest() != rec.get("contract_sha256"):
        bad.append("deployed code does not have the recorded sha256")
    deployed_to = (d.get("data") or {}).get("contract_address") or d.get("to_address")
    if str(deployed_to).lower() != addr.lower():
        bad.append(f"the deployment transaction made {deployed_to}, the record says {addr}")

    # 2. every transaction
    filed = {}  # (sender, bounty id) -> digests filed and taken, in order
    for s in rec["steps"]:
        t = tx(c, s["tx"])
        got = summary(t)
        for key in ("status", "result", "execution", "returned", "created_at"):
            ok = got[key] == s[key] or (key == "status" and {got[key], s[key]} <= {"ACCEPTED", "FINALIZED"})
            if not ok:
                bad.append(f"step {s['n']} {s['tx']}: {key} on chain {got[key]!r}, recorded {s[key]!r}")
        if str(t.get("from_address", "")).lower() != s["from"].lower():
            bad.append(f"step {s['n']}: sender on chain {t.get('from_address')}, recorded {s['from']}")
        if str(t.get("to_address", "")).lower() != addr.lower():
            bad.append(f"step {s['n']}: sent to {t.get('to_address')}, not to the recorded contract")
        if int(t.get("value") or 0) != int(s["value"]):
            bad.append(f"step {s['n']}: value on chain {t.get('value')}, recorded {s['value']}")
        # 3. digests
        r = s["returned"] if isinstance(s["returned"], dict) else {}
        if s["method"] == "file_claim" and r.get("ok") is True:
            filed.setdefault((s["from"].lower(), s["args"][0]), []).append(s["args"][1])
        if s["method"] == "judge" and r.get("ok") is True:
            bid, rule, height, salt = s["args"]
            if seal(bid, s["from"], rule, height, salt) not in filed.get((s["from"].lower(), bid), []):
                bad.append(f"step {s['n']}: the revealed rule, block and salt do not give a digest this sender filed on bounty {bid}")
        time.sleep(0.2)

    # 4. final states
    for bid, want in rec.get("bounties", {}).items():
        now = read(c, addr, "get_bounty", [bid, int(time.time())])
        for key in ("state", "poster", "claim_type", "subject_name", "block_url_template", "mining_url", "pot", "fee", "expires_at", "filed", "burned", "lead"):
            if now[key] != want[key]:
                bad.append(f"bounty {bid}: {key} is now {now[key]!r}, recorded {want[key]!r}")

    # 5. money
    t = read(c, addr, "totals")
    held = balance(c, addr)
    if str(held) != t["accounted_for"]:
        bad.append(f"balance {held} differs from locked + credited + burned = {t['accounted_for']}")

    print(f"{len(rec['steps'])} transactions, the deployed code, {len(rec.get('bounties', {}))} bounties and the balance checked against the chain; {len(bad)} mismatches")
    for b in bad:
        print("  " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
