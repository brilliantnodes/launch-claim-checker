#!/usr/bin/env python3
"""Live cases for LaunchClaimBounties on GenLayer Studio, with a record of every transaction.

    LCB_KEYS=/path/to/keys python tools/live_bounties.py [record.json] [--resume]

--resume continues an interrupted run from its record: steps and checks that
are already in the record are not done again.

Three throwaway keys (poster, hunter, copier) are read from the folder named in
LCB_KEYS (default ~/.lcb-keys; made if missing, never printed) and funded from Studio's faucet. All coins, pools and
explorer pages are fictional (Examplecoin, Controlcoin). The run takes a little
over an hour, because the contract's own waiting times are real: a filing lives
30 minutes, and a pot goes back 60 minutes after the expiry.

A filing is sealed. Its salt is kept in memory until the judgement reveals it;
from then on it is public on the chain and in this record.

The record is rewritten after every step, so an interrupted run keeps what happened.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import G, balance, client, deploy, fund, new_salt, read, seal, send  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KEYS = Path(os.environ.get("LCB_KEYS", str(Path.home() / ".lcb-keys")))
RESUME = "--resume" in sys.argv
_args = [a for a in sys.argv[1:] if a != "--resume"]
OUT = Path(_args[0]) if _args else ROOT / "examples" / "live" / "bounties-studio.json"
SITE = "https://checker.brilliantnodes.com/examples/bounty"
EXM_BLOCK, EXM_MINE = f"{SITE}/examplecoin/block/{{n}}.html", f"{SITE}/examplecoin/mining.html"
CTL_BLOCK = f"{SITE}/controlcoin/block/{{n}}.html"
TTL, MARGIN = 1800, 1800
SOURCE = ROOT / "contracts" / "launch_claim_bounties.py"

roles = {r: client(KEYS / f"lcb_studio_{r}.key") for r in ("poster", "hunter", "copier")}
C = {r: v[0] for r, v in roles.items()}
A = {r: v[1].address for r, v in roles.items()}
rec = {"network": "genlayer-studio", "chain_id": 61999, "contract_source": "contracts/launch_claim_bounties.py",
       "contract_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(), "accounts": A, "steps": [], "checks": []}
if RESUME:
    rec = json.loads(OUT.read_text())
    assert rec["accounts"] == A, "the record was made with other keys"
DONE = {s["label"]: s for s in rec["steps"]}
CHECKED = {c["label"] for c in rec["checks"]}
skew = 0.0
SEALED = {}  # (who, bounty id) -> (rule, height, salt) of the filing that was taken


def unix(iso):
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()


def now():
    """The network's clock, as seen in the last transaction's creation time."""
    return int(time.time() + skew)


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


def step(label, who, fn, args, value=0, expect=None, refused=None):
    """One transaction. refused: text the contract's refusal must contain (the call is rolled back)."""
    global skew
    if label in DONE:  # resumed run: this step is already in the record
        r = DONE[label]["returned"]
        return r if isinstance(r, dict) else {}
    sent = time.time()
    h, r = send(C[who], rec["address"], fn, args, value=value)
    if r.get("created_at"):
        skew = unix(r["created_at"]) - sent
    if refused is not None:
        ok = r["execution"] == "ERROR" and refused in json.dumps(r["returned"], default=str)
    else:
        ok = r["execution"] == "SUCCESS" and (expect is None or bool(expect(r["returned"])))
    row = {"n": len(rec["steps"]) + 1, "label": label, "who": who, "from": A[who], "method": fn, "args": args, "value": str(value),
           "tx": h, "expected": f"refused by the contract: {refused}" if refused is not None else "accepted", "as_expected": ok, **r}
    rec["steps"].append(row)
    save()
    print(f"{row['n']:2d} {'ok ' if ok else 'NOT AS EXPECTED '}{label}: {r['status']} {r['execution']} {json.dumps(r['returned'], default=str)[:160]}", flush=True)
    return r["returned"] if isinstance(r["returned"], dict) else {}


def check(label, value, want=None):
    if label in CHECKED:  # resumed run: this check is already in the record
        return
    ok = bool(value) if want is None else value == want
    rec["checks"].append({"label": label, "value": value, "want": want, "ok": ok, "at": now()})
    save()
    print(f"   check {'ok ' if ok else 'FAILED '}{label}: {json.dumps(value, default=str)[:200]}", flush=True)


def view(fn, args=None):
    return read(C["poster"], rec["address"], fn, args)


def bounty(bid):
    return view("get_bounty", [bid, now()])


def until(ts, why):
    wait = ts - now() + 5
    if wait > 0:
        print(f"   waiting {int(wait)} s for {why}", flush=True)
        time.sleep(wait)


def reconcile(label):
    """A withdrawal leaves the contract when its transaction is finalized, a minute or two after it is accepted."""
    end = time.time() + 600
    while True:
        t = view("totals")
        held = balance(C["poster"], rec["address"])
        if str(held) == t["accounted_for"] or time.time() > end:
            break
        time.sleep(10)
    name = f"{label}: the contract's balance equals locked + credited + burned"
    if name in CHECKED:
        return
    check(name, {"balance": str(held), **t})
    rec["checks"][-1]["ok"] = str(held) == t["accounted_for"]
    save()


def received(who, before, at_least):
    """Wait for a withdrawal to reach the wallet; returns what arrived, in wei."""
    end = time.time() + 600
    while balance(C[who], A[who]) - before < at_least and time.time() < end:
        time.sleep(10)
    return balance(C[who], A[who]) - before


def post(label, claim, subject, tpl, mine, minutes, pot):
    out = step(label, "poster", "post_bounty", [claim, subject, tpl, mine, now() + minutes * 60, 1000], value=pot, expect=lambda r: r.get("ok") is True)
    return out.get("id"), int(out.get("fee", 0)), int(out.get("expires_at", 0))


def file(label, who, bid, rule, height, value, expect, digest=None, taken=True):
    """A sealed filing. Only the digest goes on the chain."""
    salt = new_salt()
    out = step(label, who, "file_claim", [bid, digest or seal(bid, A[who], rule, height, salt)], value=value, expect=expect)
    if taken and out.get("ok") is True:
        SEALED[(who, bid)] = (rule, height, salt)
    return out


def judge(label, who, bid, expect=None, refused=None, reveal=None):
    rule, height, salt = reveal or SEALED[(who, bid)]
    return step(label, who, "judge", [bid, rule, height, salt], expect=expect, refused=refused)


TAKEN = lambda r: r.get("ok") is True  # noqa: E731

if not RESUME:
    for r in A:
        fund(C[r], A[r], 20)
    rec["deploy"] = deploy(C["poster"])
    rec["address"] = rec["deploy"]["address"]
    save()
    print("deployed", rec["address"], flush=True)
    rec["rules"] = view("get_rules")

# 1. Won by P1: Examplecoin block 1 pays the founders 2,000,000 EXM on top of the block reward.
b1, fee1, _ = post("1. Post a bounty: Examplecoin has no founder reward (pot 1 GEN)", "NO_FOUNDER_REWARD", "Examplecoin", EXM_BLOCK, "", 15, G)
file("1. File a sealed claim (block 1 under rule P1; the fee is burned)", "hunter", b1, "P1", 1, fee1, lambda r: r.get("ok") is True and r.get("seq") == 1)
x = bounty(b1)["filings"][0]
check("1. the filing on record shows a digest and nothing about the claim", {"rule": x["rule"], "height": x["height"], "digest_length": len(x["digest"])},
      {"rule": "", "height": -1, "digest_length": 64})
judge("1. Reveal and judge it: block 1 shows the founders' allocation", "hunter", b1, lambda r: r.get("outcome") == "PAYS_P1" and r.get("state") == "WON")
x = bounty(b1)
check("1. the bounty is won by the hunter, on the agreed amount", {"state": x["state"], "winner": x["lead"]["hunter"], "agreed": x["lead"]["agreed"]},
      {"state": "WON", "winner": A["hunter"], "agreed": {"outcome": "PAYS_P1", "block": 1, "amount": "2000000"}})
check("1. the leader's line, which every accepting validator found on its own copy of the page", x["lead"]["leader_reading"])
check("1. the pot is credited to the hunter", view("get_claimable", [A["hunter"]]), str(G))
before = balance(C["hunter"], A["hunter"])
step("1. The hunter withdraws the pot", "hunter", "withdraw", [0], expect=lambda r: r.get("amount") == str(G))
if "1. the hunter's wallet received the pot (less any transaction fee)" not in CHECKED:
    got = received("hunter", before, G * 9 // 10)
    check("1. the hunter's wallet received the pot (less any transaction fee)", {"received_wei": str(got)})
    rec["checks"][-1]["ok"] = G * 9 // 10 <= got <= G
reconcile("after case 1")

# 2. Won by M1: one miner produced 840 of the last 1,000 Examplecoin blocks.
b2, fee2, _ = post("2. Post a bounty: Examplecoin mining is decentralized (pot 2 GEN)", "DECENTRALIZED_MINING", "Examplecoin", "", EXM_MINE, 15, 2 * G)
file("2. File a sealed claim under rule M1", "hunter", b2, "M1", 0, fee2, TAKEN)
judge("2. Reveal and judge it: one miner has 840 of 1,000 blocks", "hunter", b2, lambda r: r.get("outcome") == "PAYS_M1" and r.get("state") == "WON")
x = bounty(b2)
check("2. the agreed top miner is stored; block counts are not", {"agreed": x["lead"]["agreed"], "counts_stored": "leader_reading" in x["lead"]},
      {"agreed": {"outcome": "PAYS_M1", "top_miner": "exm1qa7example0000000000000000000000001"}, "counts_stored": False})

# 3. Survives: Controlcoin's block 1 holds only the block reward.
b3, fee3, exp3 = post("3. Post a bounty: Controlcoin has no premine (pot 1 GEN, 11 minutes)", "NO_PREMINE", "Controlcoin", CTL_BLOCK, "", 11, G)
file("3. File a sealed claim on block 1", "hunter", b3, "P1", 1, fee3, TAKEN)
judge("3. Reveal and judge it: block 1 holds only the block reward", "hunter", b3, lambda r: r.get("outcome") == "NO_PAY" and r.get("state") == "OPEN")
judge("3. The same filing cannot be judged twice", "hunter", b3, refused="no live filing")

# 4. Of two paying claims, the one filed first wins, even when the other is judged first.
b4, fee4, _ = post("4. Post a bounty: Examplecoin has no premine (pot 1 GEN)", "NO_PREMINE", "Examplecoin", EXM_BLOCK, "", 15, G)
file("4. The hunter files a sealed claim (place 1 in the queue)", "hunter", b4, "P1", 1, fee4, lambda r: r.get("seq") == 1)
file("4. A second hunter files on the same block afterwards (place 2)", "copier", b4, "P1", 1, fee4, lambda r: r.get("seq") == 2)
judge("4. The second hunter is judged first: it leads, provisionally", "copier", b4, lambda r: r.get("outcome") == "PAYS_P1" and r.get("state") == "PROVISIONAL")
x = bounty(b4)
check("4. the second hunter leads; nothing is paid while an earlier filing waits", {"leader": x["lead"]["hunter"], "pot_held": x["pot_held"], "credit": view("get_claimable", [A["copier"]])},
      {"leader": A["copier"], "pot_held": str(G), "credit": "0"})
step("4. Finalizing before the window ends is refused", "copier", "finalize", [b4], refused="window ends")
judge("4. The first hunter is judged: the earlier filing takes the lead and, with nothing sent before it, wins", "hunter", b4,
      lambda r: r.get("outcome") == "PAYS_P1" and r.get("lead") is True and r.get("state") == "WON")
x = bounty(b4)
check("4. the first hunter won; the second got nothing", {"winner": x["lead"]["hunter"], "pot_held": x["pot_held"], "second_hunter_credit": view("get_claimable", [A["copier"]]),
                                                         "filings": [f["status"] for f in x["filings"]]},
      {"winner": A["hunter"], "pot_held": "0", "second_hunter_credit": "0", "filings": ["PAYS", "OUTRANKED"]})

# 5. Refusals. A refused payment is credited back to its sender; a refused reveal costs nothing.
b5, fee5, _ = post("5. Post a bounty for the refusal cases (pot 0.5 GEN)", "NO_FOUNDER_REWARD", "Examplecoin", EXM_BLOCK, "", 15, G // 2)
file("5. A filing with the wrong fee is refused and credited back", "copier", b5, "P1", 1, fee5 + 1,
     lambda r: r.get("ok") is False and r.get("refunded") == str(fee5 + 1), taken=False)
file("5. A filing whose digest is not a sha256 is refused and credited back", "copier", b5, "P1", 1, fee5,
     lambda r: r.get("ok") is False and "digest" in r.get("error", ""), digest="block 1 pays the founders", taken=False)
file("5. A filing on a bounty that does not exist is refused and credited back", "copier", "999", "P1", 1, fee5,
     lambda r: r.get("ok") is False and "no such bounty" in r.get("error", ""), taken=False)
check("5. the three refused payments are credited to the copier", view("get_claimable", [A["copier"]]), str(3 * fee5 + 1))
file("5. The hunter files a sealed claim on block 7, a page that does not exist", "hunter", b5, "P1", 7, fee5, TAKEN)
_rule, _height, salt7 = SEALED[("hunter", b5)]
file("5. A second live filing by the same hunter is refused and credited back", "hunter", b5, "P1", 1, fee5,
     lambda r: r.get("ok") is False and "live filing" in r.get("error", ""), taken=False)
judge("5. A reveal with another salt is refused", "hunter", b5, refused="do not match", reveal=("P1", 7, new_salt()))
judge("5. A reveal with another block is refused", "hunter", b5, refused="do not match", reveal=("P1", 6, salt7))
judge("5. Block 101 is outside rule P1", "hunter", b5, refused="0 to 100", reveal=("P1", 101, salt7))
judge("5. Rule M1 is not what this bounty pays on", "hunter", b5, refused="pays on", reveal=("M1", 0, salt7))
judge("5. The right reveal: the page cannot be read; the filing stays live", "hunter", b5, lambda r: r.get("outcome") == "UNREADABLE" and r.get("tries_left") == 2)
file("5. A copier files the hunter's digest, now that it is public (fee burned)", "copier", b5, "P1", 7, fee5, TAKEN,
     digest=seal(b5, A["hunter"], "P1", 7, salt7), taken=False)
judge("5. The copier cannot open it: the digest binds the filer's address", "copier", b5, refused="do not match", reveal=("P1", 7, salt7))
judge("5. Someone with no filing cannot have anything judged", "poster", b5, refused="no live filing", reveal=("P1", 7, salt7))

# 6. Wrong page: the pinned page shows block 1, the claim says block 2.
b6, fee6, _ = post("6. Post a bounty whose pinned address always shows block 1", "NO_PREMINE", "Examplecoin", f"{SITE}/examplecoin/block/1.html?n={{n}}", "", 15, G // 2)
file("6. File a sealed claim on block 2", "hunter", b6, "P1", 2, fee6, TAKEN)
judge("6. Reveal and judge it: the page shows another block number", "hunter", b6, lambda r: r.get("outcome") == "WRONG_PAGE" and r.get("tries_left") == 2)

# 7. A lead that has to wait: an earlier filing is never judged, so the pot is paid when that filing's 60 minutes are over.
b7, fee7, _ = post("7. Post a bounty: Examplecoin has no premine (pot 0.5 GEN, 20 minutes)", "NO_PREMINE", "Examplecoin", EXM_BLOCK, "", 20, G // 2)
file("7. A first filing is made on block 3 and then left alone", "copier", b7, "P1", 3, fee7, lambda r: r.get("seq") == 1)
file("7. The hunter files on block 1 afterwards", "hunter", b7, "P1", 1, fee7, lambda r: r.get("seq") == 2)
judge("7. The hunter is judged: it pays, but the earlier filing could still be judged, so the lead is provisional", "hunter", b7,
      lambda r: r.get("outcome") == "PAYS_P1" and r.get("lead") is True and r.get("state") == "PROVISIONAL")
x = bounty(b7)
window_end = int(x["window_end"])
check("7. the window ends 60 minutes after the earlier filing was sent", window_end, int(x["filings"][0]["at"]) + TTL + MARGIN)
reconcile("after cases 1 to 7")

# 3, continued: after the expiry no filing is taken, and the pot goes back only after 60 more minutes.
until(exp3, "bounty 3 to expire")
file("3. A filing after the expiry is refused and credited back", "copier", b3, "P1", 2, fee3,
     lambda r: r.get("ok") is False and "expired" in r.get("error", ""), taken=False)
step("3. Reclaiming right after the expiry is refused", "poster", "reclaim", [b3], refused="reclaimed from")
check("3. views show the bounty as expired and unclaimed", bounty(b3)["state"], "EXPIRED_UNCLAIMED")

# 7, continued: the window ends 60 minutes after the earlier filing was sent.
step("7. Finalizing before the window ends is refused", "poster", "finalize", [b7], refused="window ends")
until(window_end, "bounty 7's window to end")
step("7. Anyone finalizes: the pot is credited to the hunter", "poster", "finalize", [b7], expect=lambda r: r.get("winner") == A["hunter"] and r.get("credited") == str(G // 2))
check("7. the copier got nothing but its refunds", view("get_claimable", [A["copier"]]), str(3 * fee5 + 1 + fee3))
step("7. The hunter withdraws", "hunter", "withdraw", [0], expect=lambda r: r.get("amount") == str(3 * G + G // 2 + fee5))  # three pots, plus its own refused filing on bounty 5

# 3, the end: the poster takes the pot back.
until(exp3 + TTL + MARGIN, "bounty 3's pot to be reclaimable")
step("3. The poster reclaims the pot", "poster", "reclaim", [b3], expect=lambda r: r.get("credited") == str(G) and r.get("state") == "EXPIRED")
step("3. The poster withdraws", "poster", "withdraw", [0], expect=lambda r: r.get("amount") == str(G))
step("5. The copier withdraws its refunds", "copier", "withdraw", [0], expect=lambda r: r.get("amount") == str(3 * fee5 + 1 + fee3))
reconcile("at the end")
t = view("totals")
check("at the end: burned equals the fees of the ten filings taken", t["burned"], str(fee1 + fee2 + fee3 + 2 * fee4 + 2 * fee5 + fee6 + 2 * fee7))
rec["bounties"] = {b: bounty(b) for b in (b1, b2, b3, b4, b5, b6, b7)}
rec["summary"] = {"deployment": 1, "steps": len(rec["steps"]), "steps_as_expected": sum(1 for s in rec["steps"] if s["as_expected"]),
                  "checks": len(rec["checks"]), "checks_met": sum(1 for c in rec["checks"] if c["ok"])}
save()
print(json.dumps(rec["summary"]), flush=True)
