#!/usr/bin/env python3
"""Check the Bradbury live-run record of LaunchClaimCheckerV2 against the chain. Reads only.

    cd tools/bradbury && npm ci && cd ../..
    python tools/verify_v2_bradbury.py [examples/live/v2-bradbury.json]

1. bradbury/build/launch_claim_checker_v2.py is what tools/port_bradbury.py --pack
   makes from contracts/launch_claim_checker_v2.py today.
2. The code carried by the recorded deployment transaction is that build,
   byte for byte, and it made the recorded contract.
3. Every recorded transaction exists on Bradbury, went to the recorded
   contract from the recorded sender, calls the
   recorded method with the recorded arguments (decoded from the call data
   on the chain), and has the recorded consensus result, validator votes,
   execution result and creation time.
4. Every withdrawal carries exactly one transfer: to its own sender.
5. Every check of the run is on the contract, requested by the run's
   requester, and each bond is in its recorded final state with the recorded
   amount. (A Bradbury transaction as the node returns it does not carry the
   GEN sent with it; the record shows each refusal by the credit it left.)
   The verdict and rule of every check, and every re-check's verdict and rule,
   are read from the contract again and compared with what the run read.
6. The contract's balance equals locked + credited + burned.

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
NO_DECISION = ("UNDETERMINED", "MAJORITY_DISAGREE", "NO_MAJORITY")  # the validators did not agree: nothing stored
VOTE = {0: "NOT_VOTED", 1: "FINISHED_WITH_RETURN", 2: "FINISHED_WITH_ERROR", 3: "TIMEOUT", 4: "NONDET_DISAGREE", 5: "DETERMINISTIC_VIOLATION"}


def _throwaway_key():
    fd, path = tempfile.mkstemp(suffix=".key")
    os.write(fd, ("0x" + secrets.token_hex(32)).encode())
    os.close(fd)
    atexit.register(os.remove, path)
    return path


KEY = os.environ.get("BRADBURY_READ_KEY") or _throwaway_key()


def base_label(label: str) -> str:
    for tail in (" (sent again)", " (retry 2)", " (retry)", " (again)"):
        if label.endswith(tail):
            return label[: -len(tail)]
    return label


_REC = {}


def repeated(step: dict) -> bool:
    """A later step of the record with the same call (same label apart from a retry mark) that went through."""
    later = [x for x in _REC["steps"] if x["n"] > step["n"] and base_label(x["label"]) == base_label(step["label"])]
    return any(x.get("as_expected") and x["method"] == step["method"] and x["args"] == step["args"] for x in later)


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


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "live" / "v2-bradbury.json"
    rec = json.loads(path.read_text())
    _REC.update(rec)
    addr, bad = rec["address"], []

    # 1. the build is the source, ported and packed
    build = (ROOT / "bradbury" / "build" / "launch_claim_checker_v2.py").read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "build.py"
        subprocess.run([sys.executable, str(ROOT / "tools" / "port_bradbury.py"), str(ROOT / "contracts" / "launch_claim_checker_v2.py"), str(out), "--pack"],
                       check=True, capture_output=True)
        if out.read_bytes() != build:
            bad.append("bradbury/build/launch_claim_checker_v2.py is not what port_bradbury.py --pack makes from the source")
    if hashlib.sha256(build).hexdigest() != rec.get("build_sha256"):
        bad.append("the build does not have the sha256 recorded for the run")

    # 2. deployed code
    raw = node("tx", rec["deploy_tx"])["raw"]
    dec = raw.get("txDataDecoded") or {}
    if (dec.get("code") or "").encode() != build:
        bad.append("the code in the deployment transaction differs from the build")
    if str(dec.get("contractAddress") or raw.get("recipient") or "").lower() != addr.lower():
        bad.append("the deployment transaction did not make the recorded contract")

    # 3 and 4. every transaction
    transfers = []
    for s in rec["steps"]:
        if s["tx"] is None:  # the node refused the send itself: there is no transaction to compare
            if repeated(s):
                print(f"  note: step {s['n']} ({s['label']}): never reached the chain ({str(s['result']).splitlines()[0][:80]}); sent again and agreed later")
            else:
                bad.append(f"step {s['n']} ({s['label']}): never reached the chain and was not sent again")
            continue
        raw = node("tx", s["tx"])["raw"]
        st = str(raw.get("statusName", ""))
        result = st if st in NOTHING_STORED else raw.get("resultName")
        same = result == s["result"] or (s["result"] == "UNDETERMINED" and result in NO_DECISION)  # read at the time / once final
        if not same or raw.get("txExecutionResultName") != s["execution"]:
            bad.append(f"step {s['n']} {s['tx']}: chain {result}/{raw.get('txExecutionResultName')}, record {s['result']}/{s['execution']}")
        try:
            call = _call(_rlp_first(bytes.fromhex(str(raw.get("txCalldata"))[2:])))
        except Exception:
            call = (None, None)
        if call != (s["method"], s["args"]):
            bad.append(f"step {s['n']} {s['tx']}: the chain has {call[0]}{call[1]}, the record {s['method']}{s['args']}")
        votes = [VOTE.get(v, str(v)) for v in (raw.get("lastRound") or {}).get("validatorVotes") or []]
        if votes != s["validators"].get("votes"):
            bad.append(f"step {s['n']}: validator votes on chain {votes}, recorded {s['validators'].get('votes')}")
        if str(raw.get("createdTimestamp")) != str(s["created"]):
            bad.append(f"step {s['n']}: created at {raw.get('createdTimestamp')} on chain, recorded {s['created']}")
        if str(raw.get("sender", "")).lower() != s["from"].lower():
            bad.append(f"step {s['n']}: sender on chain {raw.get('sender')}, recorded {s['from']}")
        if str(raw.get("recipient", "")).lower() != addr.lower():
            bad.append(f"step {s['n']}: sent to {raw.get('recipient')}, not to the recorded contract")
        if s.get("as_expected") is not True:
            if s["result"] != "MAJORITY_AGREE" and (raw.get("lifecycle") or {}).get("outcome") == "undetermined" and repeated(s):
                # no majority, so nothing was stored or decided; the record shows the same call sent again and agreed
                print(f"  note: step {s['n']} ({s['label']}): no majority ({s['result']}), sent again and agreed later")
            else:
                bad.append(f"step {s['n']} ({s['label']}): the record itself says not as expected")
        if s["method"] == "withdraw" and s["execution"] == "FINISHED_WITH_RETURN":
            msgs = raw.get("messages") or []
            if len(msgs) != 1 or str(msgs[0].get("recipient", "")).lower() != s["from"].lower() or int(str(msgs[0].get("value") or 0), 0) <= 0:
                bad.append(f"step {s['n']}: the withdrawal does not carry exactly one transfer to its own sender: {msgs}")
            else:
                transfers.append((s["who"], int(str(msgs[0]["value"]), 0)))
        time.sleep(0.2)

    # 5. every check and every bond, as the contract shows them now
    for case, c in rec["cases"].items():
        got = node("read", addr, "get_check", json.dumps([c["id"]]))["result"]
        for chk in rec.get("checks", []):  # what the run read from the views, read again now
            lab, want = chk["label"], chk.get("want")
            if not lab.startswith(f"case {case}: "):
                continue
            if " is " in lab and lab.split(": ", 1)[1].startswith("check ") and isinstance(want, list):
                if [got["result"]["verdict"], got["result"]["rule"]] != want[:2]:
                    bad.append(f"case {case}: stored {got['result']['verdict']} {got['result']['rule']}, the run read {want[:2]}")
            if "re-check found" in lab:
                rc = got["bond"].get("recheck") or {}
                now_ = [rc.get("verdict"), rc.get("rule")] if isinstance(want, list) else rc.get("rule")
                if now_ != want:
                    bad.append(f"case {case}: re-check stored {now_}, the run read {want}")
        if str(got["requester"]).lower() != rec["accounts"]["requester"].lower():
            bad.append(f"case {case}: check {c['id']} was requested by {got['requester']}")
        want = rec.get("final_states", {}).get(case)
        if want and got["bond"]["state"] != want:
            bad.append(f"case {case}: bond is now {got['bond']['state']}, recorded {want}")
        if want and str(got["bond"]["amount"]) != rec["bond_wei"]:
            bad.append(f"case {case}: bonded {got['bond']['amount']} wei, recorded {rec['bond_wei']}")
        if want == "OVERTURNED" and int(got["bond"].get("burned") or 0) != int(rec["bond_wei"]) // 2:
            bad.append(f"case {case}: {got['bond'].get('burned')} wei burned, not half the bond")
    checks = rec.get("checks", [])
    for i, chk in enumerate(checks):
        if chk["ok"]:
            continue
        note = next((n for n in rec.get("after_the_run", []) if n.get("supersedes") == chk["label"]), None)
        if note and note.get("chain"):
            # an excuse only stands on a value read again from the chain now
            ch = note["chain"]
            v = node("read", addr, ch["view"], json.dumps(ch.get("args", [])))["result"]
            for k in ch.get("path", []):
                v = v.get(k) if isinstance(v, dict) else None
            if str(v) == str(ch["want"]):
                print(f"  note: the run's check '{chk['label']}' failed (it read {chk.get('value')!r}); {note['note']} Read from the chain now: {v}")
                continue
            bad.append(f"record check failed: {chk['label']}; the chain now gives {v!r}, the note says {ch['want']!r}")
            continue
        case = chk["label"].split(":", 1)[0][5:] if chk["label"].startswith("case ") else None
        later_pass = any(c["label"] == chk["label"] and c["ok"] for c in checks[i + 1:])
        moved_on = case is not None and chk.get("value") == rec.get("final_states", {}).get(case) and chk.get("value") is not None
        if later_pass or moved_on:
            # a read that passed later (an end state read before a refused send was sent again), or a re-read on a
            # resume that found the case's recorded final state (the state had moved on)
            why = "passed when read again later in the run" if later_pass else "read again on a resume, it found the case's final state"
            print(f"  note: the run's check '{chk['label']}' failed (it read {chk.get('value')!r}); {why}")
            continue
        bad.append(f"record check failed: {chk['label']} (it read {chk.get('value')!r})")

    # the windows and the number of checks, read from the contract
    rules = node("read", addr, "get_rules", "[]")["result"]
    w = rules.get("windows_seconds") or {}
    if [w.get(k) for k in ("bond_win", "ch_win", "grace", "rc_win")] != rec.get("windows_seconds"):
        bad.append(f"windows on chain {w}, recorded {rec.get('windows_seconds')}")
    agreed = sum(1 for x in rec["steps"] if x["method"] == "check_claim" and x.get("as_expected") is True)
    t0 = node("read", addr, "totals", "[]")["result"]
    if int(t0.get("checks", -1)) != agreed:
        bad.append(f"the contract holds {t0.get('checks')} checks; the record has {agreed} agreed checks")

    # 6. money
    t = node("read", addr, "totals", "[]")["result"]
    held = node("balance", addr)["result"]
    if str(held) != t["accounted_for"] or int(t["accounted_for"]) != int(t["locked"]) + int(t["credited"]) + int(t.get("burned", 0)):
        bad.append(f"balance {held} differs from locked + credited + burned = {t['accounted_for']}")

    print(f"{len(rec['steps'])} steps ({sum(1 for x in rec['steps'] if x['tx'])} transactions), the deployed code, {len(rec['cases'])} checks and the balance checked against the chain; {len(bad)} mismatches")
    for who, wei in transfers:
        print(f"  withdrawal by the {who}: one transfer of {wei} wei to its own address")
    print(f"  totals: {json.dumps(t)}; balance {held}")
    for b in bad:
        print("  " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
