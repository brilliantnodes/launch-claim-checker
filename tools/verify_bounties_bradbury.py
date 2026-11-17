#!/usr/bin/env python3
"""Check the Bradbury live-run record of LaunchClaimBounties against the chain. Reads only.

    cd tools/bradbury && npm ci && cd ../..
    python tools/verify_bounties_bradbury.py [examples/live/bounties-bradbury.json]

1. bradbury/build/launch_claim_bounties.py is what tools/port_bradbury.py --pack
   makes from contracts/launch_claim_bounties.py today.
2. The code carried by the recorded deployment transaction is that build,
   byte for byte, and it made the recorded contract.
3. Every recorded transaction exists on Bradbury, went to the recorded
   contract from the recorded sender, calls the recorded method with the
   recorded arguments (decoded from the call data on the chain), and has the
   recorded consensus result, validator votes, execution result and
   creation time.
4. For every filing that was judged, the rule, block and salt revealed in the
   judgement give the digest that was filed.
5. Every withdrawal carries exactly one transfer: to its own sender.
6. Each bounty, read from the contract now, is in the recorded final state
   with the recorded winner and agreed facts.
7. The contract's balance equals locked + credited + burned.

A throwaway key is made for the reads (or BRADBURY_READ_KEY names one);
nothing is signed or sent. Exit code 1 on any mismatch.
"""
import atexit
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "tools" / "bradbury"
NOTHING_STORED = ("UNDETERMINED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT", "CANCELED")
VOTE = {0: "NOT_VOTED", 1: "FINISHED_WITH_RETURN", 2: "FINISHED_WITH_ERROR", 3: "TIMEOUT", 4: "NONDET_DISAGREE", 5: "DETERMINISTIC_VIOLATION"}


def _throwaway_key():
    fd, path = tempfile.mkstemp(suffix=".key")
    os.write(fd, ("0x" + secrets.token_hex(32)).encode())
    os.close(fd)
    atexit.register(os.remove, path)
    return path


KEY = os.environ.get("BRADBURY_READ_KEY") or _throwaway_key()


def node(*a):
    p = subprocess.run(["node", "gl.mjs", *a], cwd=JS, capture_output=True, text=True, timeout=300, env={**os.environ, "BRADBURY_KEY_FILE": KEY})
    return json.loads([ln for ln in p.stdout.splitlines() if ln.startswith("{")][-1])


def _rlp_first(data: bytes) -> bytes:
    """The first item of an RLP list (Bradbury wraps the call data as [call data, leader-only flag])."""
    def item(i):
        b = data[i]
        if b < 0x80:
            return i, 1
        if b < 0xB8:
            return i + 1, b - 0x80
        if b < 0xC0:
            n = b - 0xB7
            return i + 1 + n, int.from_bytes(data[i + 1 : i + 1 + n], "big")
        if b < 0xF8:
            return i + 1, b - 0xC0
        n = b - 0xF7
        return i + 1 + n, int.from_bytes(data[i + 1 : i + 1 + n], "big")

    start, _length = item(0)  # the list
    at, n = item(start)
    return data[at : at + n]


def _call(data: bytes):
    """Decode GenLayer call data (LEB128 numbers; the low three bits are the type). Returns (method, args)."""
    pos = 0

    def num():
        nonlocal pos
        out = shift = 0
        while True:
            b = data[pos]
            pos += 1
            out |= (b & 0x7F) << shift
            shift += 7
            if b < 0x80:
                return out

    def take(n):
        nonlocal pos
        pos += n
        return data[pos - n : pos]

    def value():
        v = num()
        kind, n = v & 7, v >> 3
        if kind == 0:
            return {0: None, 1: False, 2: True}[n] if n < 3 else "0x" + take(20).hex()
        if kind == 1:
            return n
        if kind == 2:
            return -n - 1
        if kind == 3:
            return take(n)
        if kind == 4:
            return take(n).decode("utf-8")
        if kind == 5:
            return [value() for _ in range(n)]
        if kind == 6:
            return {take(num()).decode("utf-8"): value() for _ in range(n)}
        raise ValueError("unknown call data type")

    d = value()
    return d.get("method", d.get("")), d.get("args", [])


def seal(bounty_id, address, rule, height, salt) -> str:
    return hashlib.sha256(f"{bounty_id}|{str(address).lower()}|{rule}|{int(height)}|{salt}".encode("utf-8")).hexdigest()


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "live" / "bounties-bradbury.json"
    rec = json.loads(path.read_text())
    addr, bad = rec["address"], []

    # 1. the build is the source, ported and packed
    build = (ROOT / "bradbury" / "build" / "launch_claim_bounties.py").read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "build.py"
        subprocess.run([sys.executable, str(ROOT / "tools" / "port_bradbury.py"), str(ROOT / "contracts" / "launch_claim_bounties.py"), str(out), "--pack"],
                       check=True, capture_output=True)
        if out.read_bytes() != build:
            bad.append("bradbury/build/launch_claim_bounties.py is not what port_bradbury.py --pack makes from the source")
    if hashlib.sha256(build).hexdigest() != rec.get("build_sha256"):
        bad.append("the build does not have the sha256 recorded for the run")

    # 2. deployed code
    raw = node("tx", rec["deploy"]["tx"])["raw"]
    dec = raw.get("txDataDecoded") or {}
    if (dec.get("code") or "").encode() != build:
        bad.append("the code in the deployment transaction differs from the build")
    if str(dec.get("contractAddress") or raw.get("recipient") or "").lower() != addr.lower():
        bad.append("the deployment transaction did not make the recorded contract")

    # 3 to 5. every transaction
    filed, transfers = {}, []
    for s in rec["steps"]:
        raw = node("tx", s["tx"])["raw"]
        st = str(raw.get("statusName", ""))
        result = st if st in NOTHING_STORED else raw.get("resultName")
        if (result, raw.get("txExecutionResultName")) != (s["result"], s["execution"]):
            bad.append(f"step {s['n']} {s['tx']}: chain {result}/{raw.get('txExecutionResultName')}, record {s['result']}/{s['execution']}")
        try:
            call = _call(_rlp_first(bytes.fromhex(str(raw.get("txCalldata"))[2:])))
        except Exception:
            call = (None, None)
        if call != (s["method"], s["args"]):
            bad.append(f"step {s['n']} {s['tx']}: the chain has {call[0]}{call[1]}, the record {s['method']}{s['args']}")
        votes = [VOTE.get(v, str(v)) for v in (raw.get("lastRound") or {}).get("validatorVotes") or []]
        if "validators" in s and votes != s["validators"].get("votes"):
            bad.append(f"step {s['n']}: validator votes on chain {votes}, recorded {s['validators'].get('votes')}")
        if "created" in s and str(raw.get("createdTimestamp")) != str(s["created"]):
            bad.append(f"step {s['n']}: created at {raw.get('createdTimestamp')} on chain, recorded {s['created']}")
        if str(raw.get("sender", "")).lower() != s["from"].lower():
            bad.append(f"step {s['n']}: sender on chain {raw.get('sender')}, recorded {s['from']}")
        if str(raw.get("recipient", "")).lower() != addr.lower():
            bad.append(f"step {s['n']}: sent to {raw.get('recipient')}, not to the recorded contract")
        done = s["result"] == "MAJORITY_AGREE" and s["execution"] == "FINISHED_WITH_RETURN"
        if s["method"] == "file_claim" and done:
            filed.setdefault((s["from"].lower(), s["args"][0]), []).append(s["args"][1])
        if s["method"] == "judge" and done:
            bid, rule, height, salt = s["args"]
            if seal(bid, s["from"], rule, height, salt) not in filed.get((s["from"].lower(), bid), []):
                bad.append(f"step {s['n']}: the revealed rule, block and salt do not give a digest this sender filed on bounty {bid}")
        if s["method"] == "withdraw" and done:
            msgs = raw.get("messages") or []
            if len(msgs) != 1 or str(msgs[0].get("recipient", "")).lower() != s["from"].lower() or int(msgs[0].get("value") or 0) <= 0:
                bad.append(f"step {s['n']}: the withdrawal does not carry exactly one transfer to its own sender: {msgs}")
            else:
                transfers.append((s["who"], int(msgs[0]["value"])))
        time.sleep(0.2)

    # 6. final states
    now = int(time.time())
    for bid, want in rec.get("bounties", {}).items():
        got = node("read", addr, "get_bounty", json.dumps([bid, now]))["result"]
        for key in ("state", "poster", "claim_type", "subject_name", "block_url_template", "mining_url", "pot", "fee", "expires_at", "filed", "burned", "lead"):
            if got[key] != want[key]:
                bad.append(f"bounty {bid}: {key} is now {got[key]!r}, recorded {want[key]!r}")

    # 7. money
    t = node("read", addr, "totals", "[]")["result"]
    held = node("balance", addr)["result"]
    if str(held) != t["accounted_for"]:
        bad.append(f"balance {held} differs from locked + credited + burned = {t['accounted_for']}")

    print(f"{len(rec['steps'])} transactions, the deployed code, {len(rec.get('bounties', {}))} bounties and the balance checked against the chain; {len(bad)} mismatches")
    for who, wei in transfers:
        print(f"  withdrawal by the {who}: one transfer of {wei} wei to its own address")
    print(f"  totals: {json.dumps(t)}; balance {held}")
    for b in bad:
        print("  " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
