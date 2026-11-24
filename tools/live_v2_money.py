#!/usr/bin/env python3
"""Bond and challenge cases for LaunchClaimCheckerV2 on GenLayer Studio, with a record of every transaction.

    LCC2_KEYS=/path/to/keys python tools/live_v2_money.py [record.json] [--resume]

Companion to tools/live_v2.py (the free checks). A fresh deployment with the
600-second floor windows; each case makes its own check and bonds it at once,
because a bond must follow its check within 10 minutes. A check on which the
validators do not agree records nothing; it is tried once more, and both
attempts stay in the record. Needs genlayer-py 0.19 or later (Studio fees).

Cases (all coins and both explorers fictional, both run by Brilliant Nodes):
  A  Examplecoin NO_FOUNDER_REWARD  bonded, two challengers, re-check   -> UPHELD
  B  Controlcoin NO_PREMINE         bonded, no challenger               -> RELEASED
  C  Flipcoin NO_FOUNDER_REWARD     bonded, challenged; both explorers then correct block 1 -> OVERTURNED
  D  Driftcoin NO_FOUNDER_REWARD    bonded, challenged; only Blockfield corrects block 1    -> NOT_CONFIRMED
  E  Examplecoin NO_PREMINE         bonded, challenged, nobody re-checks                    -> NOT_CONFIRMED
  F  free checks: explorer B shows another coin (W1); an instruction planted on B (verdict
     unchanged); bonds refused on a mining verdict, on "explorers disagree" and on FAIR_LAUNCH;
     challenges refused (wrong amount, the requester, a second time, after the window);
     collect; withdraw. An overturned bond burns half: at the end the contract holds exactly
     the burned GEN, and nothing is locked or credited.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import G, balance, client, fund, read  # noqa: E402
from studio_fees import deploy, send  # noqa: E402
import v2_pages  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KEYS = Path(os.environ.get("LCC2_KEYS", str(Path.home() / ".lcc2-keys")))
RESUME = "--resume" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(_args[0]) if _args else ROOT / "examples" / "live" / "v2-studio-money.json"
SOURCE = ROOT / "contracts" / "launch_claim_checker_v2.py"
CHECKER_REPO = Path(os.environ.get("CHECKER_REPO", str(ROOT)))
DEMO_REPO = Path(os.environ.get("DEMO_REPO", str(ROOT.parent / "demo-explorer")))
WIN = 600
A = "https://checker.brilliantnodes.com/v2/{c}-block-1.html"
B = "https://brilliantnodes.github.io/demo-explorer/{c}/block-1.html"
A_MINE = "https://checker.brilliantnodes.com/v2/examplecoin-mining.html"
B_MINE = "https://brilliantnodes.github.io/demo-explorer/examplecoin/pools.html"
B_PLANTED = "https://brilliantnodes.github.io/demo-explorer/examplecoin/pools-annotated.html"
BOND = G

roles = {r: client(KEYS / f"lcc2_studio_{r}.key") for r in ("requester", "challenger1", "challenger2")}
C = {r: v[0] for r, v in roles.items()}
ADDR = {r: v[1].address for r, v in roles.items()}
rec = {"network": "genlayer-studio", "chain_id": 61999, "contract_source": "contracts/launch_claim_checker_v2.py",
       "contract_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(), "windows_seconds": [WIN] * 4,
       "accounts": ADDR, "steps": [], "checks": [], "page_changes": [], "cases": {}}
if RESUME:
    rec = json.loads(OUT.read_text())
    assert rec["accounts"] == ADDR, "the record was made with other keys"
DONE = {s["label"]: s for s in rec["steps"]}


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


def unix(iso):
    return int(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp())


def step(label, who, fn, args, value=0, expect=None):
    if label in DONE:
        return DONE[label]
    due()
    h, s = send(C[who], rec["address"], fn, args, value, sender=ADDR[who])
    ret = s.get("returned")
    as_expected = None
    if isinstance(expect, str) and expect.startswith("refused:"):
        as_expected = isinstance(ret, dict) and ret.get("ok") is False and expect[8:] in str(ret.get("error", ""))
    elif isinstance(expect, dict):
        as_expected = isinstance(ret, dict) and all(ret.get(k) == v for k, v in expect.items())
    entry = {"label": label, "who": who, "from": ADDR[who], "fn": fn, "args": args, "value": str(value), "tx": h,
             **s, "expected": expect, "as_expected": as_expected}
    rec["steps"].append(entry)
    DONE[label] = entry
    save()
    mark = "OK " if as_expected else ("?? " if as_expected is None else "NO ")
    print(f"{mark}{label}: {s.get('result')} {json.dumps(ret, default=str)[:300]}", flush=True)
    return entry


def check_with_retry(case, args, expect):
    """A check; if the validators did not agree (nothing recorded), once more."""
    for attempt in ("", " (retry)"):
        e = step(f"case {case} check{attempt}", "requester", "check_claim", args, 0, expect)
        ret = e.get("returned")
        if isinstance(ret, dict) and ret.get("id"):
            rec["cases"].setdefault(case, {})["id"] = ret["id"]
            save()
            return ret["id"]
    raise SystemExit(f"case {case}: no agreed check after two attempts")


def wait_until(t, why):
    while True:
        left = t - time.time()
        if left <= 0:
            return
        print(f"... waiting {int(left)} s for {why}", flush=True)
        time.sleep(min(left, 60))


def check_view(label, cond, detail):
    rec["checks"].append({"label": label, "ok": bool(cond), "detail": detail})
    save()
    print(("ok   " if cond else "FAIL ") + label, flush=True)


def correct_pages(coin):
    """Correct one coin's fictional pages (tools/v2_pages.py), sending due outcome steps while the pages go live."""
    if any(p["coin"] == coin for p in rec["page_changes"]):
        return
    ch = v2_pages.correct(coin, "Studio live run", DEMO_REPO, CHECKER_REPO, wait=due)
    rec["page_changes"].append(ch)
    save()
    print(f"pages corrected for {coin}: {ch}", flush=True)


def times(case):
    """The bond's own times, as the contract returned them."""
    return {k: int(v) for k, v in DONE[f"bond case {case}"]["returned"].items() if k in ("close", "rc_open", "rc_end", "nc_from")}


OUTCOMES = []  # (case, time key, offset, label, who, fn, value, expect), run as soon as each is due
_busy = [False]


def due():
    if _busy[0]:
        return
    _busy[0] = True
    try:
        for case, key, off, label, who, fn, value, expect in OUTCOMES:
            if label in DONE or f"bond case {case}" not in DONE:
                continue
            if time.time() >= times(case)[key] + off:
                step(label, who, fn, [rec["cases"][case]["id"]], value, expect)
    finally:
        _busy[0] = False


# ------------------------------------------------------------------ setup

for r in ADDR:
    if balance(C[r], ADDR[r]) < 15 * G:
        fund(C[r], ADDR[r], 20)
if "address" not in rec:
    rec["deploy"] = deploy(C["requester"], SOURCE.read_text(), [WIN, WIN, WIN, WIN])
    rec["address"] = rec["deploy"]["address"]
    save()
    print("deployed", rec["deploy"], flush=True)

# ------------------------------------------------------------------ checks, each bonded at once

P1 = {"verdict": "CONTRADICTED", "rule": "BOTH:P1"}
CASES = {
    "A": ([A.format(c="examplecoin"), B.format(c="examplecoin"), "Examplecoin", "NO_FOUNDER_REWARD", "No founder reward"], P1),
    "B": ([A.format(c="controlcoin"), B.format(c="controlcoin"), "Controlcoin", "NO_PREMINE", "No premine"], {"verdict": "SUPPORTED", "rule": "BOTH:P2"}),
    "C": ([A.format(c="flipcoin"), B.format(c="flipcoin"), "Flipcoin", "NO_FOUNDER_REWARD", ""], P1),
    "D": ([A.format(c="driftcoin"), B.format(c="driftcoin"), "Driftcoin", "NO_FOUNDER_REWARD", ""], P1),
    "E": ([A.format(c="examplecoin"), B.format(c="examplecoin"), "Examplecoin", "NO_PREMINE", ""], P1),
}
OUTCOMES += [
    ("B", "close", 5, "challenge B after the window", "challenger2", "challenge", BOND, "refused:window has closed"),
    ("A", "rc_open", 5, "recheck A", "challenger1", "recheck", 0, {"ok": True, "decided": True, "state": "UPHELD"}),
    ("B", "rc_open", 5, "settle B (no challenger)", "challenger1", "settle", 0, {"ok": True, "state": "RELEASED"}),
    ("C", "rc_open", 5, "recheck C (both explorers corrected block 1)", "challenger1", "recheck", 0, {"ok": True, "decided": True, "state": "OVERTURNED"}),
    ("D", "rc_open", 5, "recheck D (only Blockfield corrected block 1)", "challenger2", "recheck", 0, {"ok": True, "decided": True, "state": "NOT_CONFIRMED"}),
    ("E", "nc_from", 5, "settle E (no re-check was run)", "challenger1", "settle", 0, {"ok": True, "state": "NOT_CONFIRMED"}),
]
ids = {}
for case, (args, expect) in CASES.items():
    ids[case] = check_with_retry(case, args, expect)
    step(f"bond case {case}", "requester", "bond", [ids[case]], BOND, {"ok": True, "bonded": str(BOND)})
    if case == "A":
        step("challenge A by challenger1", "challenger1", "challenge", [ids["A"]], BOND, {"ok": True, "challenger": 1})
        step("challenge A by challenger2", "challenger2", "challenge", [ids["A"]], BOND, {"ok": True, "challenger": 2})
        step("challenge A by the requester", "requester", "challenge", [ids["A"]], BOND, "refused:the requester cannot")
        step("challenge A again by challenger1", "challenger1", "challenge", [ids["A"]], BOND, "refused:already challenged")
    elif case == "B":
        step("challenge B with the wrong amount", "challenger1", "challenge", [ids["B"]], BOND - 1, "refused:exactly the bond")
    elif case == "C":
        step("challenge C by challenger1", "challenger1", "challenge", [ids["C"]], BOND, {"ok": True, "challenger": 1})
        correct_pages("flipcoin")
    elif case == "D":
        step("challenge D by challenger2", "challenger2", "challenge", [ids["D"]], BOND, {"ok": True, "challenger": 1})
        correct_pages("driftcoin")
    elif case == "E":
        step("challenge E by challenger1", "challenger1", "challenge", [ids["E"]], BOND, {"ok": True, "challenger": 1})

mine = check_with_retry("F-mining", [A_MINE, B_MINE, "Examplecoin", "DECENTRALIZED_MINING", ""], {"verdict": "CONTRADICTED", "rule": "BOTH:M1"})
step("bond on a mining verdict", "requester", "bond", [mine], BOND, "refused:BOTH:P1 or BOTH:P2")
split = check_with_retry("F-disagree", [A.format(c="splitcoin"), B.format(c="splitcoin"), "Splitcoin", "NO_FOUNDER_REWARD", ""], {"verdict": "UNDETERMINED", "rule": "D1_EXPLORERS_DISAGREE"})
step("bond on explorers that disagree", "requester", "bond", [split], BOND, "refused:BOTH:P1 or BOTH:P2")
fair = check_with_retry("F-fair", [A.format(c="examplecoin"), B.format(c="examplecoin"), "Examplecoin", "FAIR_LAUNCH", "Fair launch"], P1)
step("bond on a FAIR_LAUNCH verdict", "requester", "bond", [fair], BOND, "refused:NO_PREMINE or NO_FOUNDER_REWARD")
check_with_retry("F-wrong-page", [A.format(c="examplecoin"), B.format(c="controlcoin"), "Examplecoin", "NO_FOUNDER_REWARD", ""], {"verdict": "UNDETERMINED", "rule": "W1_WRONG_PAGE"})
check_with_retry("F-planted", [A_MINE, B_PLANTED, "Examplecoin", "DECENTRALIZED_MINING", ""], {"verdict": "CONTRADICTED", "rule": "BOTH:M1"})

# ------------------------------------------------------------------ outcomes

while any(o[3] not in DONE for o in OUTCOMES):
    due()
    left = [times(o[0])[o[1]] + o[2] - time.time() for o in OUTCOMES if o[3] not in DONE]
    if left:
        print(f"... next outcome step in {int(max(0, min(left)))} s", flush=True)
        time.sleep(max(5, min(30, min(left))))

# ------------------------------------------------------------------ collect and withdraw

owed = {("A", "requester"): 3 * BOND, ("A", "challenger1"): 0, ("A", "challenger2"): 0, ("B", "requester"): BOND,
        ("C", "requester"): 0, ("C", "challenger1"): BOND + (BOND - BOND // 2), ("D", "requester"): BOND, ("D", "challenger2"): BOND,
        ("E", "requester"): BOND, ("E", "challenger1"): BOND}
for (case, who), amount in owed.items():
    step(f"collect {case} by {who}", who, "collect", [ids[case]], 0, {"ok": True, "credited": str(amount)})
for who in ADDR:
    claim = int(read(C[who], rec["address"], "get_claimable", [ADDR[who]]))
    if claim > 0:
        step(f"withdraw {who}", who, "withdraw", [0], 0, {"ok": True, "amount": str(claim)})

# ------------------------------------------------------------------ checks against the views

v = {c: read(C["requester"], rec["address"], "get_check", [ids[c]]) for c in ids}
for c, st in (("A", "UPHELD"), ("B", "RELEASED"), ("C", "OVERTURNED"), ("D", "NOT_CONFIRMED"), ("E", "NOT_CONFIRMED")):
    check_view(f"case {c} bond state {st}", v[c]["bond"]["state"] == st, v[c]["bond"])
check_view("case C shows the overturning verdict SUPPORTED", (v["C"]["bond"].get("recheck") or {}).get("verdict") == "SUPPORTED", v["C"]["bond"].get("recheck"))
check_view("case D re-check: the explorers disagree", (v["D"]["bond"].get("recheck") or {}).get("rule") == "D1_EXPLORERS_DISAGREE", v["D"]["bond"].get("recheck"))
check_view("challengers of case A", [x.lower() for x in read(C["requester"], rec["address"], "get_challengers", [ids["A"]])] == [ADDR["challenger1"].lower(), ADDR["challenger2"].lower()], None)
t = read(C["requester"], rec["address"], "totals", [])
check_view("totals: nothing locked or credited; half of case C's bond burned", t["locked"] == "0" and t["credited"] == "0" and t["burned"] == str(BOND // 2), t)
def settled_balance():
    """Studio makes each withdrawal's transfer as a transaction of its own, a little after the withdrawal: read the
    balance until it stops changing (up to five minutes)."""
    last, reads = None, 0
    while reads < 11:
        now = balance(C["requester"], rec["address"])
        reads += 1
        if now == BOND // 2 or now == last:
            break
        last = now
        time.sleep(30)
    return now, reads


held, reads = settled_balance()
check_view("contract balance equals the burned GEN", held == BOND // 2, {"balance": held, "reads": reads})
check_view("case C: half the bond burned", v["C"]["bond"].get("burned") == BOND // 2, v["C"]["bond"].get("burned"))
check_view("case F-wrong-page stored in short form", read(C["requester"], rec["address"], "get_check", [rec["cases"]["F-wrong-page"]["id"]])["result"]["a"].keys() <= {"cls", "rule"}, None)
rec["summary"] = {"steps": len(rec["steps"]), "steps_as_expected": sum(1 for s in rec["steps"] if s["as_expected"]),
                  "checks": len(rec["checks"]), "checks_ok": sum(1 for c in rec["checks"] if c["ok"])}
save()
print(json.dumps(rec["summary"]), flush=True)
