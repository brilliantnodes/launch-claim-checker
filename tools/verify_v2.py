#!/usr/bin/env python3
"""Check a Studio live-run record of LaunchClaimCheckerV2 against the chain. Reads only.

    python tools/verify_v2.py examples/live/v2-studio-money.json [examples/live/v2-studio-checks.json ...]

For each record:
1. The code deployed by the recorded deployment transaction is, byte for
   byte, contracts/launch_claim_checker_v2.py in this repository, and the
   deployment made the recorded contract.
2. Every recorded transaction exists on Studio, went to the recorded
   contract from the recorded sender with the recorded value, calls the
   recorded method with the recorded arguments (decoded from the call data
   on the chain), and has the recorded consensus result, validator votes,
   execution result, return value and creation time.
3. Every check the record numbers is on the contract now with the recorded
   verdict and rule; each bonded case is in its recorded final state.
4. The contract's balance equals locked + credited (totals()), and the
   record's own expectations all held.

A throwaway key is made for the reads; nothing is signed or sent. Exit code 1 on any mismatch.
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from genlayer_py.abi import calldata  # noqa: E402

from bounty import balance, client, read, summary, tx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v


def verify(path: Path, c) -> list:
    rec = json.loads(path.read_text())
    addr, bad = rec["address"], []

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

    for n, s in enumerate(rec["steps"], 1):
        t = tx(c, s["tx"])
        got = summary(t)
        try:
            call = calldata.decode(base64.b64decode((t.get("data") or {}).get("calldata") or ""))
        except Exception:
            call = {}
        if (call.get("method", call.get("")), plain(call.get("args", []))) != (s["fn"], plain(s["args"])):
            bad.append(f"step {n} {s['tx']}: the chain has {call.get('method', call.get(''))}{call.get("args")}, the record {s['fn']}{s['args']}")
        for key in ("result", "execution", "returned", "created_at", "votes"):
            if key in s and plain(got.get(key)) != plain(s[key]):
                bad.append(f"step {n} {s['tx']}: {key} on chain {got.get(key)!r}, recorded {s[key]!r}")
        if str(t.get("from_address", "")).lower() != s["from"].lower():
            bad.append(f"step {n}: sender on chain {t.get('from_address')}, recorded {s['from']}")
        if str(t.get("to_address", "")).lower() != addr.lower():
            bad.append(f"step {n}: sent to {t.get('to_address')}, not to the recorded contract")
        if int(t.get("value") or 0) != int(s["value"]):
            bad.append(f"step {n}: value on chain {t.get('value')}, recorded {s['value']}")
        if s.get("as_expected") is False and not s.get("explained"):
            bad.append(f"step {n} ({s['label']}): the record itself says not as expected")

    for s in rec["steps"]:
        r = s.get("returned")
        if s["fn"] == "check_claim" and isinstance(r, dict) and r.get("id"):
            v = read(c, addr, "get_check", [r["id"]])
            if [v["result"]["verdict"], v["result"]["rule"]] != [r["verdict"], r["rule"]]:
                bad.append(f"check {r['id']}: now {v['result']['verdict']} {v['result']['rule']}, recorded {r['verdict']} {r['rule']}")
    for case, final in (rec.get("final_states") or {}).items():
        v = read(c, addr, "get_check", [rec["cases"][case]["id"]])
        if v["bond"]["state"] != final:
            bad.append(f"case {case}: bond now {v['bond']['state']}, recorded {final}")
    t = read(c, addr, "totals", [])
    held = balance(c, addr)
    if held != int(t["locked"]) + int(t["credited"]):
        bad.append(f"balance {held} != locked {t['locked']} + credited {t['credited']}")
    for chk in rec.get("checks", []):
        if not chk["ok"]:
            bad.append(f"record check failed: {chk['label']}")
    print(f"{path.name}: contract {addr}, {len(rec['steps'])} transactions, balance {held} wei = locked + credited: {'OK' if not bad else 'MISMATCH'}")
    return bad


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or [ROOT / "examples" / "live" / "v2-studio-money.json", ROOT / "examples" / "live" / "v2-studio-checks.json"]
    c, _acct = client()
    bad = []
    for p in paths:
        bad += [f"{p.name}: {b}" for b in verify(p, c)]
    for b in bad:
        print("  -", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
