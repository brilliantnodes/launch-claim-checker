#!/usr/bin/env python3
"""Live cases for LaunchClaimBounties on GenLayer Testnet Bradbury Phase 2 (GenVM v0.6 build).

    cd tools/bradbury && npm ci && cd ../..
    LCB_KEYS=/path/to/keys python tools/live_bounties_bradbury.py [record.json]

Two testnet wallets, poster and hunter, whose keys stay in files outside the
repository (LCB_KEYS/lcb_bradbury_poster.key and lcb_bradbury_hunter.key; never
printed). The poster must hold Bradbury test GEN; it passes some on to the
hunter. All coins, pools and explorer pages are fictional.

Bradbury transactions carry no return value. Every step here is recorded
with the chain's own outcome (consensus result and execution result) and
with what the contract's views show afterwards.

The waiting times are the contract's own: the last case takes back an
unclaimed pot 60 minutes after its expiry, so the run takes about 90 minutes.
The record is rewritten after every step.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from genlayer_py import create_account

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import new_salt, seal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "tools" / "bradbury"
KEYS = Path(os.environ.get("LCB_KEYS", "/home/claude/keys"))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "live" / "bounties-bradbury.json"
BUILD = ROOT / "bradbury" / "build" / "launch_claim_bounties.py"
SITE = "https://checker.brilliantnodes.com/examples/bounty"
EXM_BLOCK, EXM_MINE = f"{SITE}/examplecoin/block/{{n}}.html", f"{SITE}/examplecoin/mining.html"
CTL_BLOCK = f"{SITE}/controlcoin/block/{{n}}.html"
G = 10**18
TTL, MARGIN = 1800, 1800
NOTHING_STORED = ("UNDETERMINED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT", "CANCELED")
KEY = {r: str(KEYS / f"lcb_bradbury_{r}.key") for r in ("poster", "hunter")}
A = {r: create_account(Path(KEY[r]).read_text().strip()).address for r in KEY}
rec = {"network": "testnet-bradbury-phase-2", "chain_id": 4221, "build": "bradbury/build/launch_claim_bounties.py (GenVM v0.6)",
       "build_sha256": hashlib.sha256(BUILD.read_bytes()).hexdigest(), "accounts": A, "steps": [], "checks": []}


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


def node(role, *args, timeout=1800):
    """A write is never sent twice: once it has a hash, a failure only means waiting longer for that transaction."""
    env = {**os.environ, "BRADBURY_KEY_FILE": KEY[role]}
    d = {"ok": False, "error": "no result"}
    for _attempt in range(3):
        try:
            p = subprocess.run(["node", "gl.mjs", *args], cwd=JS, capture_output=True, text=True, timeout=timeout, env=env)
            out = p.stdout
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        objs = [json.loads(ln) for ln in out.splitlines() if ln.startswith("{")]
        sent = next((o["sent"] for o in objs if "sent" in o), None)
        d = next((o for o in reversed(objs) if "ok" in o), {"ok": False, "error": "no result"})
        if d.get("ok"):
            return d
        if args[0] in ("write", "deploy") and (sent or d.get("hash")):
            return wait(sent or d.get("hash"))
        time.sleep(15)
    return d


def tx(h):
    return (node("poster", "tx", h, timeout=300).get("raw")) or {}


def decided(raw):
    st = str(raw.get("statusName", ""))
    return st in NOTHING_STORED or (st in ("ACCEPTED", "FINALIZED") and raw.get("resultName") not in (None, "", "IDLE"))


def wait(h, final=False):
    for _ in range(240):
        raw = tx(h)
        if (str(raw.get("statusName")) == "FINALIZED") if final else decided(raw):
            return {"ok": True, "hash": h, "raw": raw}
        time.sleep(10)
    return {"ok": False, "hash": h, "error": "not decided after 40 minutes", "raw": tx(h)}


def transfers(h) -> list:
    """The GEN transfers a transaction carries (a withdrawal carries one, to its own sender)."""
    return [{"to": m.get("recipient"), "wei": str(m.get("value"))} for m in (tx(h).get("messages") or [])]


def read(fn, args=None):
    d = node("poster", "read", rec["address"], fn, json.dumps(args or [], default=str), timeout=300)
    if not d.get("ok"):
        raise RuntimeError(f"read {fn}: {d.get('error')}")
    return d["result"]


def balance(addr) -> int:
    return int(node("poster", "balance", addr, timeout=120)["result"])


def now() -> int:
    return int(time.time())


def bounty(bid):
    return read("get_bounty", [bid, now()])


def step(label, role, fn, args, value=0, refused=False, payees=""):
    """One transaction. refused: the contract is expected to roll the call back."""
    t0 = time.time()
    d = node(role, "write", rec["address"], fn, json.dumps(args, default=str), str(value), payees)
    h = d.get("hash")
    if h and not decided(d.get("raw") or {}):
        d = wait(h)
    # A leader or validator timeout can still execute after the leader rotates, so wait for the final outcome.
    if h and str((d.get("raw") or {}).get("statusName")) in ("LEADER_TIMEOUT", "VALIDATORS_TIMEOUT"):
        d = wait(h, final=True)
    raw = d.get("raw") or {}
    st = str(raw.get("statusName", ""))
    result = st if st in NOTHING_STORED else (raw.get("resultName") or d.get("error"))
    execution = raw.get("txExecutionResultName")
    ok = result == "MAJORITY_AGREE" and ((execution != "FINISHED_WITH_RETURN") if refused else (execution == "FINISHED_WITH_RETURN"))
    row = {"n": len(rec["steps"]) + 1, "label": label, "who": role, "from": A[role], "method": fn, "args": args, "value": str(value), "tx": h,
           "expected": "refused by the contract" if refused else "accepted", "result": result, "execution": execution,
           "created": raw.get("createdTimestamp"), "seconds": int(time.time() - t0), "as_expected": ok}
    rec["steps"].append(row)
    save()
    print(f"{row['n']:2d} {'ok ' if ok else 'NOT AS EXPECTED '}{label}: {result} {execution} {h} ({row['seconds']} s)", flush=True)
    return row


def check(label, value, want=None):
    ok = bool(value) if want is None else value == want
    rec["checks"].append({"label": label, "value": value, "want": want, "ok": ok, "at": now()})
    save()
    print(f"   check {'ok ' if ok else 'FAILED '}{label}: {json.dumps(value, default=str)[:220]}", flush=True)
    return ok


def post(label, claim, subject, tpl, mine, minutes, pot):
    before = int(read("get_count"))
    step(label, "poster", "post_bounty", [claim, subject, tpl, mine, now() + minutes * 60, 1000], value=pot)
    bid = str(int(read("get_count")))
    b = bounty(bid)
    check(f"{label}: the bounty is on record", {"new": int(bid) == before + 1, "pot": b["pot"], "state": b["state"], "poster": b["poster"]},
          {"new": True, "pot": str(pot), "state": "OPEN", "poster": A["poster"]})
    return bid, int(b["fee"]), int(b["expires_at"])


def file(label, role, bid, rule, height, fee):
    salt = new_salt()
    digest = seal(bid, A[role], rule, height, salt)
    step(label, role, "file_claim", [bid, digest], value=fee)
    mine = [f for f in bounty(bid)["filings"] if f["digest"] == digest and f["hunter"].lower() == A[role].lower()]
    check(f"{label}: the sealed filing is on record and shows nothing about the claim", [(f["status"], f["rule"], f["height"]) for f in mine], [("LIVE", "", -1)])
    return rule, height, salt


def judged(bid):
    log = bounty(bid)["log"]
    return log[-1] if log else {}


def judge(label, role, bid, reveal, want, tries=3):
    """The validators read a live page with their own models. If they do not agree, nothing is stored
    and the filing stays live, so the same reveal is sent again; every attempt is recorded."""
    rule, height, salt = reveal
    for attempt in range(1, tries + 1):
        before = len(bounty(bid)["log"])
        row = step(label if attempt == 1 else f"{label} (attempt {attempt})", role, "judge", [bid, rule, height, salt])
        b = bounty(bid)
        if len(b["log"]) > before or row["as_expected"]:
            got = b["log"][-1].get("outcome") if len(b["log"]) > before else None
            check(f"{label}: outcome on record", {"outcome": got, "state": b["state"]}, want)
            return b
        row["as_expected"] = row["result"] in NOTHING_STORED or row["result"] != "MAJORITY_AGREE"  # no agreement: nothing stored, try again
        row["note"] = "the validators did not agree; nothing was stored and the filing stayed live"
        save()
    return bounty(bid)


def until(ts, why):
    left = ts - now() + 20
    if left > 0:
        print(f"   waiting {int(left)} s for {why}", flush=True)
        time.sleep(left)


# ---- funding and deployment
start = {r: balance(A[r]) for r in A}
rec["balances_at_start_wei"] = {r: str(v) for r, v in start.items()}
print("balances", rec["balances_at_start_wei"], flush=True)
if start["hunter"] < G:
    give = min(15 * G // 10, start["poster"] // 2)
    d = node("poster", "send", A["hunter"], str(give))
    rec["funding"] = {"from": A["poster"], "to": A["hunter"], "wei": str(give), "tx": d.get("hash")}
    for _ in range(60):
        if balance(A["hunter"]) >= start["hunter"] + give:
            break
        time.sleep(10)
    rec["funding"]["arrived"] = balance(A["hunter"]) >= start["hunter"] + give
    save()
    print("funded hunter", rec["funding"], flush=True)

b0 = balance(A["poster"])
d = node("poster", "deploy", str(BUILD), "[]")
raw = d.get("raw") or {}
rec["deploy"] = {"tx": d.get("hash"), "address": raw.get("recipient"), "result": raw.get("resultName"), "execution": raw.get("txExecutionResultName")}
rec["address"] = raw.get("recipient")
save()
print("deployed", rec["deploy"], flush=True)
if rec["deploy"]["execution"] != "FINISHED_WITH_RETURN" or not rec["address"]:
    raise SystemExit("deployment failed")
time.sleep(20)
rec["deploy"]["cost_wei"] = str(b0 - balance(A["poster"]))
rec["rules"] = read("get_rules")
save()

# 1. Won by P1: Examplecoin block 1 pays the founders 2,000,000 EXM on top of the block reward.
POT = G // 10
b1, fee1, _ = post("1. Post a bounty: Examplecoin has no founder reward (pot 0.1 GEN)", "NO_FOUNDER_REWARD", "Examplecoin", EXM_BLOCK, "", 25, POT)
r1 = file("1. The hunter files a sealed claim (the fee is burned)", "hunter", b1, "P1", 1, fee1)
step("1. A reveal with another salt is refused", "hunter", "judge", [b1, "P1", 1, new_salt()], refused=True)
x = judge("1. Reveal and judge it: block 1 shows the founders' allocation", "hunter", b1, r1, {"outcome": "PAYS_P1", "state": "WON"})
check("1. won by the hunter on the agreed amount", {"winner": (x["lead"] or {}).get("hunter"), "agreed": (x["lead"] or {}).get("agreed")},
      {"winner": A["hunter"], "agreed": {"outcome": "PAYS_P1", "block": 1, "amount": "2000000"}})
check("1. the leader's line, found by every accepting validator on its own copy of the page", (x["lead"] or {}).get("leader_reading"))
check("1. the pot is credited to the hunter", read("get_claimable", [A["hunter"]]), str(POT))

# 2. Won by M1: one miner produced 840 of the last 1,000 Examplecoin blocks.
b2, fee2, _ = post("2. Post a bounty: Examplecoin mining is decentralized (pot 0.1 GEN)", "DECENTRALIZED_MINING", "Examplecoin", "", EXM_MINE, 25, POT)
r2 = file("2. The hunter files a sealed claim under rule M1", "hunter", b2, "M1", 0, fee2)
x = judge("2. Reveal and judge it: one miner has 840 of 1,000 blocks", "hunter", b2, r2, {"outcome": "PAYS_M1", "state": "WON"})
check("2. the agreed top miner is stored; block counts are not", {"agreed": (x["lead"] or {}).get("agreed"), "counts_stored": "leader_reading" in (x["lead"] or {})},
      {"agreed": {"outcome": "PAYS_M1", "top_miner": "exm1qa7example0000000000000000000000001"}, "counts_stored": False})

# 3. Survives: Controlcoin's block 1 holds only the block reward. The pot goes back to the poster.
POT3 = G // 20
b3, fee3, exp3 = post("3. Post a bounty: Controlcoin has no premine (pot 0.05 GEN, 12 minutes)", "NO_PREMINE", "Controlcoin", CTL_BLOCK, "", 12, POT3)
r3 = file("3. The hunter files a sealed claim on block 1", "hunter", b3, "P1", 1, fee3)
judge("3. Reveal and judge it: block 1 holds only the block reward", "hunter", b3, r3, {"outcome": "NO_PAY", "state": "OPEN"})
step("3. The same filing cannot be judged twice", "hunter", "judge", [b3, *r3], refused=True)

# 4. The hunter withdraws both pots. On Bradbury the transaction carries a fee allocation for the transfer to the caller.
step("4. The hunter withdraws both pots", "hunter", "withdraw", [0], payees=A["hunter"])
check("4. nothing is left credited to the hunter", read("get_claimable", [A["hunter"]]), "0")
# The wallet's balance is no measure here: it also gets back the unused part of earlier transactions' fee budgets.
# The transfer itself is on the transaction.
check("4. the withdrawal carries one transfer: both pots, to the hunter", transfers(rec["steps"][-1]["tx"]), [{"to": A["hunter"], "wei": str(2 * POT)}])

# 3, continued: after the expiry the pot goes back only after 60 more minutes.
until(exp3, "bounty 3 to expire")
step("3. Reclaiming right after the expiry is refused", "poster", "reclaim", [b3], refused=True)
check("3. views show the bounty as expired and unclaimed", bounty(b3)["state"], "EXPIRED_UNCLAIMED")
until(exp3 + TTL + MARGIN, "bounty 3's pot to be reclaimable")
step("3. The poster reclaims the pot", "poster", "reclaim", [b3])
check("3. the pot is credited back to the poster", {"state": bounty(b3)["state"], "credit": read("get_claimable", [A["poster"]])}, {"state": "EXPIRED", "credit": str(POT3)})
step("3. The poster withdraws", "poster", "withdraw", [0], payees=A["poster"])
check("3. the withdrawal carries one transfer: the pot, to the poster", transfers(rec["steps"][-1]["tx"]), [{"to": A["poster"], "wei": str(POT3)}])
wait(rec["steps"][-1]["tx"], final=True)
time.sleep(30)

t = read("totals")
held = balance(rec["address"])
check("at the end: burned equals the fees of the three filings taken", t["burned"], str(fee1 + fee2 + fee3))
check("at the end: nothing locked, nothing credited", {"locked": t["locked"], "credited": t["credited"]}, {"locked": "0", "credited": "0"})
check("at the end: the contract's balance equals locked + credited + burned", {"balance": str(held), **t})
rec["checks"][-1]["ok"] = str(held) == t["accounted_for"]
rec["bounties"] = {b: bounty(b) for b in (b1, b2, b3)}
rec["balances_at_end_wei"] = {r: str(balance(A[r])) for r in A}
rec["summary"] = {"transactions": len(rec["steps"]) + 1, "as_expected": sum(1 for s in rec["steps"] if s["as_expected"]), "steps": len(rec["steps"]),
                  "checks_ok": sum(1 for c in rec["checks"] if c["ok"]), "checks": len(rec["checks"])}
save()
print(json.dumps(rec["summary"]), flush=True)
