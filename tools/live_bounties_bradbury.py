#!/usr/bin/env python3
"""Live cases for LaunchClaimBounties on GenLayer Testnet Bradbury Phase 2 (GenVM v0.6 build).

    cd tools/bradbury && npm ci && cd ../..
    LCB_KEYS=/path/to/keys python tools/live_bounties_bradbury.py [record.json]

Three testnet wallets (poster, hunter, copier) whose keys stay in files
outside the repository: LCB_KEYS/lcb_bradbury_<role>.key, never printed.
Together they must hold about 2.5 Bradbury test GEN; the run moves GEN
between them as needed and uses almost none of it (a transaction's fee
budget is paid up front and the unused part comes back when it is
finalized). All coins, pools and explorer pages are fictional.

Bradbury transactions carry no return value. Every step here is recorded
with the chain's own outcome (consensus result, execution result, and each
validator's vote, which on Bradbury is the way its own execution ended) and with what the contract's views show afterwards.

The same seven cases as tools/live_bounties.py runs on Studio. The waiting
times are the contract's own (60 minutes twice), so the run takes about 100
minutes. The record is rewritten after every step.
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
KEYS = Path(os.environ.get("LCB_KEYS", str(Path.home() / ".lcb-keys")))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "live" / "bounties-bradbury.json"
BUILD = ROOT / "bradbury" / "build" / "launch_claim_bounties.py"
SITE = "https://checker.brilliantnodes.com/examples/bounty"
EXM_BLOCK, EXM_MINE = f"{SITE}/examplecoin/block/{{n}}.html", f"{SITE}/examplecoin/mining.html"
CTL_BLOCK = f"{SITE}/controlcoin/block/{{n}}.html"
G = 10**18
TTL, MARGIN = 1800, 1800
NOTHING_STORED = ("UNDETERMINED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT", "CANCELED")
# A Bradbury validator's vote is the way its own execution ended (genlayer-js, voteTypeNumberToName).
VOTE = {0: "NOT_VOTED", 1: "FINISHED_WITH_RETURN", 2: "FINISHED_WITH_ERROR", 3: "TIMEOUT", 4: "NONDET_DISAGREE", 5: "DETERMINISTIC_VIOLATION"}
ROLES = ("poster", "hunter", "copier")
KEY = {r: str(KEYS / f"lcb_bradbury_{r}.key") for r in ROLES}
A = {r: create_account(Path(KEY[r]).read_text().strip()).address for r in ROLES}
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


def give(frm, to, wei):
    """Move test GEN between the run's own wallets."""
    before = balance(A[to])
    d = node(frm, "send", A[to], str(wei))
    for _ in range(60):
        if balance(A[to]) >= before + wei:
            break
        time.sleep(10)
    row = {"from": A[frm], "to": A[to], "wei": str(wei), "tx": d.get("hash"), "arrived": balance(A[to]) >= before + wei}
    rec.setdefault("funding", []).append(row)
    save()
    print("moved test GEN", row, flush=True)


def step(label, role, fn, args, value=0, refused=False, payees=""):
    """One transaction. refused: the contract is expected to roll the call back."""
    for _ in range(40):  # the fee budget is paid up front; wait for earlier refunds if the wallet is low
        if balance(A[role]) >= value + 15 * G // 100:
            break
        time.sleep(15)
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
    votes = [VOTE.get(v, str(v)) for v in (raw.get("lastRound") or {}).get("validatorVotes") or []]
    ok = result == "MAJORITY_AGREE" and ((execution != "FINISHED_WITH_RETURN") if refused else (execution == "FINISHED_WITH_RETURN"))
    row = {"n": len(rec["steps"]) + 1, "label": label, "who": role, "from": A[role], "method": fn, "args": args, "value": str(value), "tx": h,
           "expected": "refused by the contract" if refused else "accepted", "result": result, "execution": execution,
           "validators": {"of": len(votes), "same_as_the_result": sum(1 for v in votes if v == execution), "votes": votes},
           "created": raw.get("createdTimestamp"), "seconds": int(time.time() - t0), "as_expected": ok}
    rec["steps"].append(row)
    save()
    print(f"{row['n']:2d} {'ok ' if ok else 'NOT AS EXPECTED '}{label}: {result} {execution} {row['validators']['same_as_the_result']} of {row['validators']['of']} validators {h} ({row['seconds']} s)", flush=True)
    return row


def check(label, value, want=None):
    """Compare what the contract's views show with what is expected. A view read right after a transaction
    can still show the state before it, so a value given as a function is read again, up to a minute."""
    reads = 0
    while True:
        got = value() if callable(value) else value
        reads += 1
        ok = bool(got) if want is None else got == want
        if ok or not callable(value) or reads >= 7:
            break
        time.sleep(10)
    value = got
    rec["checks"].append({"label": label, "value": value, "want": want, "ok": ok, "reads": reads, "at": now()})
    save()
    print(f"   check {'ok ' if ok else 'FAILED '}{label}: {json.dumps(value, default=str)[:220]}", flush=True)
    return ok


def post(label, claim, subject, tpl, mine, minutes, pot):
    before = int(read("get_count"))
    step(label, "poster", "post_bounty", [claim, subject, tpl, mine, now() + minutes * 60, 1000], value=pot)
    for _ in range(12):  # the view may lag the transaction by a few seconds
        if int(read("get_count")) > before:
            break
        time.sleep(10)
    bid = str(int(read("get_count")))

    def seen():
        b = bounty(bid)
        return {"new": int(bid) == before + 1, "pot": b["pot"], "state": b["state"], "poster": b["poster"]}

    check(f"{label}: the bounty is on record", seen, {"new": True, "pot": str(pot), "state": "OPEN", "poster": A["poster"]})
    b = bounty(bid)
    return bid, int(b["fee"]), int(b["expires_at"])


def file(label, role, bid, rule, height, fee, digest=None):
    """A sealed filing. Only the digest goes on the chain."""
    salt = new_salt()
    digest = digest or seal(bid, A[role], rule, height, salt)
    step(label, role, "file_claim", [bid, digest], value=fee)
    mine = lambda: [[f["status"], f["rule"], f["height"]] for f in bounty(bid)["filings"] if f["digest"] == digest and f["hunter"].lower() == A[role].lower()]  # noqa: E731
    check(f"{label}: the sealed filing is on record and shows no rule and no block", mine, [["LIVE", "", -1]])
    return rule, height, salt


def judge(label, role, bid, reveal, want, tries=3):
    """The validators read a live page with their own models. If they do not agree, nothing is stored
    and the filing stays live, so the same reveal is sent again; every attempt is recorded."""
    rule, height, salt = reveal
    judged = lambda b: [e for e in b["log"] if e.get("what") == "JUDGED" and e["hunter"].lower() == A[role].lower()]  # noqa: E731
    for attempt in range(1, tries + 1):
        before = len(judged(bounty(bid)))
        row = step(label if attempt == 1 else f"{label} (attempt {attempt})", role, "judge", [bid, rule, height, salt])
        if row["as_expected"]:

            def seen():
                b = bounty(bid)
                mine = judged(b)
                return {"outcome": mine[-1].get("outcome") if len(mine) > before else None, "state": b["state"]}

            check(f"{label}: outcome on record", seen, want)
            return bounty(bid)
        row["as_expected"] = row["result"] in NOTHING_STORED or row["result"] != "MAJORITY_AGREE"  # no agreement: nothing stored, try again
        row["note"] = "the validators did not agree; nothing was stored and the filing stayed live"
        save()
    return bounty(bid)


def until(ts, why):
    left = ts - now() + 20
    if left > 0:
        print(f"   waiting {int(left)} s for {why}", flush=True)
        time.sleep(left)


# ---- test GEN where it is needed, then the deployment
start = {r: balance(A[r]) for r in ROLES}
rec["balances_at_start_wei"] = {r: str(v) for r, v in start.items()}
print("balances", rec["balances_at_start_wei"], flush=True)
NEED = {"poster": 9 * G // 10, "hunter": 7 * G // 10, "copier": 5 * G // 10}
for role in ROLES:
    short = NEED[role] - balance(A[role])
    if short > 0:
        donor = max(ROLES, key=lambda r: balance(A[r]) - NEED[r])
        give(donor, role, short + G // 20)

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
rec["deploy"]["fee_budget_paid_up_front_wei"] = str(b0 - balance(A["poster"]))
rec["rules"] = read("get_rules")
save()

# 1. Won by P1: Examplecoin block 1 pays the founders 2,000,000 EXM on top of the block reward.
POT = G // 20
b1, fee1, _ = post("1. Post a bounty: Examplecoin has no founder reward (pot 0.05 GEN)", "NO_FOUNDER_REWARD", "Examplecoin", EXM_BLOCK, "", 30, POT)
r1 = file("1. The hunter files a sealed claim (the fee is burned)", "hunter", b1, "P1", 1, fee1)
step("1. A reveal with another salt is refused", "hunter", "judge", [b1, "P1", 1, new_salt()], refused=True)
x = judge("1. Reveal and judge it: block 1 shows the founders' allocation", "hunter", b1, r1, {"outcome": "PAYS_P1", "state": "WON"})
check("1. won by the hunter on the agreed amount", lambda: {"winner": (x["lead"] or {}).get("hunter"), "agreed": (x["lead"] or {}).get("agreed")},
      {"winner": A["hunter"], "agreed": {"outcome": "PAYS_P1", "block": 1, "amount": "2000000"}})
check("1. the leader's line, found by every accepting validator on its own copy of the page", lambda: (x["lead"] or {}).get("leader_reading"))
check("1. the pot is credited to the hunter", lambda: read("get_claimable", [A["hunter"]]),
      str(POT))

# 2. Won by M1: one miner produced 840 of the last 1,000 Examplecoin blocks.
b2, fee2, _ = post("2. Post a bounty: Examplecoin mining is decentralized (pot 0.05 GEN)", "DECENTRALIZED_MINING", "Examplecoin", "", EXM_MINE, 30, POT)
r2 = file("2. The hunter files a sealed claim under rule M1", "hunter", b2, "M1", 0, fee2)
x = judge("2. Reveal and judge it: one miner has 840 of 1,000 blocks", "hunter", b2, r2, {"outcome": "PAYS_M1", "state": "WON"})
check("2. the agreed top miner is stored; block counts are not", lambda: {"agreed": (x["lead"] or {}).get("agreed"), "counts_stored": "leader_reading" in (x["lead"] or {})},
      {"agreed": {"outcome": "PAYS_M1", "top_miner": "exm1qa7example0000000000000000000000001"}, "counts_stored": False})

# 3. Survives: Controlcoin's block 1 holds only the block reward. The pot goes back to the poster.
b3, fee3, exp3 = post("3. Post a bounty: Controlcoin has no premine (pot 0.05 GEN, 12 minutes)", "NO_PREMINE", "Controlcoin", CTL_BLOCK, "", 12, POT)
r3 = file("3. The hunter files a sealed claim on block 1", "hunter", b3, "P1", 1, fee3)
judge("3. Reveal and judge it: block 1 holds only the block reward", "hunter", b3, r3, {"outcome": "NO_PAY", "state": "OPEN"})
step("3. The same filing cannot be judged twice", "hunter", "judge", [b3, *r3], refused=True)

# 4. Of two paying claims, the one filed first wins, even when the other is judged first.
b4, fee4, _ = post("4. Post a bounty: Examplecoin has no premine (pot 0.05 GEN)", "NO_PREMINE", "Examplecoin", EXM_BLOCK, "", 30, POT)
r4h = file("4. The hunter files a sealed claim (place 1 in the queue)", "hunter", b4, "P1", 1, fee4)
r4c = file("4. A second hunter files on the same block afterwards (place 2)", "copier", b4, "P1", 1, fee4)
x = judge("4. The second hunter is judged first: it leads, provisionally", "copier", b4, r4c, {"outcome": "PAYS_P1", "state": "PROVISIONAL"})
check("4. the second hunter leads; nothing is paid while an earlier filing waits", lambda: {"leader": (x["lead"] or {}).get("hunter"), "pot_held": x["pot_held"], "credit": read("get_claimable", [A["copier"]])},
      {"leader": A["copier"], "pot_held": str(POT), "credit": "0"})
step("4. Finalizing before the window ends is refused", "copier", "finalize", [b4], refused=True)
x = judge("4. The first hunter is judged: the earlier filing takes the lead and, with nothing sent before it, wins", "hunter", b4, r4h, {"outcome": "PAYS_P1", "state": "WON"})
check("4. the first hunter won; the second got nothing", lambda: {"winner": (x["lead"] or {}).get("hunter"), "pot_held": x["pot_held"], "second_hunter_credit": read("get_claimable", [A["copier"]]),
                                                         "filings": [f["status"] for f in x["filings"]]},
      {"winner": A["hunter"], "pot_held": "0", "second_hunter_credit": "0", "filings": ["PAYS", "OUTRANKED"]})

# 5. Refusals. A refused payment is credited back to its sender; a refused reveal costs nothing.
b5, fee5, _ = post("5. Post a bounty for the refusal cases (pot 0.05 GEN)", "NO_FOUNDER_REWARD", "Examplecoin", EXM_BLOCK, "", 30, POT)
step("5. A filing with the wrong fee is taken by the network but refused by the contract", "copier", "file_claim", [b5, seal(b5, A["copier"], "P1", 1, new_salt())], value=fee5 + 1)
check("5. the refused payment is credited back to its sender, and no filing is on record", lambda: {"credit": read("get_claimable", [A["copier"]]), "filings": len(bounty(b5)["filings"])},
      {"credit": str(fee5 + 1), "filings": 0})
r5 = file("5. The hunter files a sealed claim on block 7, a page that does not exist", "hunter", b5, "P1", 7, fee5)
step("5. Block 101 is outside rule P1", "hunter", "judge", [b5, "P1", 101, r5[2]], refused=True)
step("5. Rule M1 is not what this bounty pays on", "hunter", "judge", [b5, "M1", 0, r5[2]], refused=True)
x = judge("5. The right reveal: the page cannot be read; the filing stays live", "hunter", b5, r5, {"outcome": "UNREADABLE", "state": "OPEN"})
check("5. the filing is still live, with two tries left", lambda: [[f["status"], f["tries"]] for f in x["filings"]],
      [["LIVE", 2]])
file("5. A copier files the hunter's digest, now that it is public (fee burned)", "copier", b5, "P1", 7, fee5, digest=seal(b5, A["hunter"], *r5))
step("5. The copier cannot open it: the digest binds the filer's address", "copier", "judge", [b5, *r5], refused=True)
step("5. Someone with no filing cannot have anything judged", "poster", "judge", [b5, *r5], refused=True)

# 6. Wrong page: the pinned page shows block 1, the claim says block 2.
b6, fee6, _ = post("6. Post a bounty whose pinned address always shows block 1", "NO_PREMINE", "Examplecoin", f"{SITE}/examplecoin/block/1.html?n={{n}}", "", 30, POT)
r6 = file("6. The hunter files a sealed claim on block 2", "hunter", b6, "P1", 2, fee6)
x = judge("6. Reveal and judge it: the page shows another block number", "hunter", b6, r6, {"outcome": "WRONG_PAGE", "state": "OPEN"})
check("6. the filing is still live, with two tries left", lambda: [[f["status"], f["tries"]] for f in x["filings"]],
      [["LIVE", 2]])

# 7. A lead that has to wait: an earlier filing is never judged, so the pot is paid when that filing's 60 minutes are over.
b7, fee7, _ = post("7. Post a bounty: Examplecoin has no premine (pot 0.05 GEN)", "NO_PREMINE", "Examplecoin", EXM_BLOCK, "", 30, POT)
file("7. A first filing is made on block 3 and then left alone", "copier", b7, "P1", 3, fee7)
r7 = file("7. The hunter files on block 1 afterwards", "hunter", b7, "P1", 1, fee7)
x = judge("7. The hunter is judged: it pays, but the earlier filing could still be judged, so the lead is provisional", "hunter", b7, r7, {"outcome": "PAYS_P1", "state": "PROVISIONAL"})
window_end = int(x["window_end"])
check("7. the window ends 60 minutes after the earlier filing was sent", lambda: window_end,
      int(x["filings"][0]["at"]) + TTL + MARGIN)
step("7. Finalizing before the window ends is refused", "poster", "finalize", [b7], refused=True)

# 3, continued: after the expiry no filing is taken, and the pot goes back only after 60 more minutes.
until(exp3, "bounty 3 to expire")
before = read("get_claimable", [A["copier"]])
step("3. A filing after the expiry is taken by the network but refused by the contract", "copier", "file_claim", [b3, seal(b3, A["copier"], "P1", 2, new_salt())], value=fee3)
check("3. that payment is credited back", lambda: int(read("get_claimable", [A["copier"]])) - int(before),
      fee3)
step("3. Reclaiming right after the expiry is refused", "poster", "reclaim", [b3], refused=True)
check("3. views show the bounty as expired and unclaimed", lambda: bounty(b3)["state"],
      "EXPIRED_UNCLAIMED")

# 7, continued.
until(window_end, "bounty 7's window to end")
step("7. Anyone finalizes: the pot is credited to the hunter", "poster", "finalize", [b7])
check("7. won by the hunter", lambda: (lambda b: {"state": b["state"], "winner": (b["lead"] or {}).get("hunter"), "pot_held": b["pot_held"]})(bounty(b7)),
      {"state": "WON", "winner": A["hunter"], "pot_held": "0"})
check("7. the hunter is credited four pots; the copier only its two refused payments", lambda: {"hunter": read("get_claimable", [A["hunter"]]), "copier": read("get_claimable", [A["copier"]])},
      {"hunter": str(4 * POT), "copier": str(fee5 + 1 + fee3)})
# On Bradbury a withdrawal carries a fee allocation for the transfer to the caller. The wallet's balance is no
# measure of it (unused fee budgets of earlier transactions come back to it too); the transfer is on the transaction.
step("7. The hunter withdraws", "hunter", "withdraw", [0], payees=A["hunter"])
check("7. the withdrawal carries one transfer: four pots, to the hunter", lambda: transfers(rec["steps"][-1]["tx"]),
      [{"to": A["hunter"], "wei": str(4 * POT)}])
step("5. The copier withdraws its refunds", "copier", "withdraw", [0], payees=A["copier"])
check("5. the withdrawal carries one transfer: the two refused payments, to the copier", lambda: transfers(rec["steps"][-1]["tx"]),
      [{"to": A["copier"], "wei": str(fee5 + 1 + fee3)}])

# 3, the end: the poster takes the pot back.
until(exp3 + TTL + MARGIN, "bounty 3's pot to be reclaimable")
step("3. The poster reclaims the pot", "poster", "reclaim", [b3])
check("3. the pot is credited back to the poster", lambda: {"state": bounty(b3)["state"], "credit": read("get_claimable", [A["poster"]])},
      {"state": "EXPIRED", "credit": str(POT)})
step("3. The poster withdraws", "poster", "withdraw", [0], payees=A["poster"])
check("3. the withdrawal carries one transfer: the pot, to the poster", lambda: transfers(rec["steps"][-1]["tx"]),
      [{"to": A["poster"], "wei": str(POT)}])
for s in rec["steps"][-3:]:
    wait(s["tx"], final=True)
time.sleep(30)

FEES = fee1 + fee2 + fee3 + 2 * fee4 + 2 * fee5 + fee6 + 2 * fee7
check("at the end: burned equals the fees of the ten filings taken", lambda: read("totals")["burned"], str(FEES))
check("at the end: nothing credited; locked is the two pots nobody won (bounties 5 and 6)", lambda: {k: v for k, v in read("totals").items() if k in ("locked", "credited")},
      {"locked": str(2 * POT), "credited": "0"})
check("at the end: the contract's balance equals locked + credited + burned", lambda: {"balance": str(balance(rec["address"])), "accounted_for": read("totals")["accounted_for"]},
      {"balance": str(FEES + 2 * POT), "accounted_for": str(FEES + 2 * POT)})
rec["bounties"] = {b: bounty(b) for b in (b1, b2, b3, b4, b5, b6, b7)}
rec["balances_at_end_wei"] = {r: str(balance(A[r])) for r in ROLES}
rec["summary"] = {"deployment": 1, "steps": len(rec["steps"]), "steps_as_expected": sum(1 for s in rec["steps"] if s["as_expected"]),
                  "checks": len(rec["checks"]), "checks_met": sum(1 for c in rec["checks"] if c["ok"])}
save()
print(json.dumps(rec["summary"]), flush=True)
