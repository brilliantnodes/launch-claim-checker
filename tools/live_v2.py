#!/usr/bin/env python3
"""Live cases for LaunchClaimCheckerV2 on GenLayer Studio, with a record of every transaction.

    LCC2_KEYS=/path/to/keys python tools/live_v2.py [record.json] [--resume] [--only-checks]

Needs genlayer-py 0.19 or later: Studio now requires a fee distribution on
every transaction (tools/studio_fees.py). Three throwaway keys (requester, challenger1, challenger2) are read from the
folder in LCC2_KEYS (made if missing, never printed) and funded from Studio's
faucet. The contract is deployed with the 600-second floor windows, so one run
takes about 45 minutes. Two explorers are used, both fictional and both run by
Brilliant Nodes: Examplescan (checker.brilliantnodes.com/v2/) and Blockfield
(brilliantnodes.github.io/demo-explorer/).

Two cases need a page to change after the challenge: Flipcoin (both explorers
correct block 1, so the re-check overturns the verdict) and Driftcoin (only
Blockfield does, so the explorers now disagree and the challenge is not
confirmed). The script makes those pages with tools/make_v2_pages.py
--corrected and pushes them (CHECKER_REPO and DEMO_REPO point to the two clones);
the commits are kept in the record.

--only-checks runs the six free checks (no GEN) and stops.
The record is rewritten after every step, so an interrupted run keeps what happened.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import G, balance, client, fund, read  # noqa: E402
from studio_fees import deploy, send  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KEYS = Path(os.environ.get("LCC2_KEYS", str(Path.home() / ".lcc2-keys")))
RESUME = "--resume" in sys.argv
ONLY_CHECKS = "--only-checks" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(_args[0]) if _args else ROOT / "examples" / "live" / "v2-studio.json"
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
       "accounts": ADDR, "steps": [], "checks": [], "page_changes": []}
if RESUME:
    rec = json.loads(OUT.read_text())
    assert rec["accounts"] == ADDR, "the record was made with other keys"
DONE = {s["label"]: s for s in rec["steps"]}
paid_in = sum(int(s["value"]) for s in rec["steps"] if s.get("value"))


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


def unix(iso):
    return int(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp())


def step(label, who, fn, args, value=0, expect=None):
    """One transaction. expect: a dict of fields the returned value must contain, or "refused:<text>"."""
    global paid_in
    if label in DONE:
        return DONE[label]
    h, s = send(C[who], rec["address"], fn, args, value, sender=ADDR[who])
    ret = s.get("returned")
    ok = s.get("result") not in (None, "UNDETERMINED") and s.get("status") in ("ACCEPTED", "FINALIZED")
    as_expected = None
    if isinstance(expect, str) and expect.startswith("refused:"):
        as_expected = isinstance(ret, dict) and ret.get("ok") is False and expect[8:] in str(ret.get("error", ""))
    elif isinstance(expect, dict):
        as_expected = isinstance(ret, dict) and all(ret.get(k) == v for k, v in expect.items())
    elif isinstance(expect, str) and expect.startswith("error:"):
        as_expected = expect[6:] in str(ret)
    entry = {"label": label, "who": who, "from": ADDR[who], "fn": fn, "args": args, "value": str(value), "tx": h,
             **s, "expected": expect, "as_expected": as_expected, "ok": ok}
    if value:
        paid_in += value
    rec["steps"].append(entry)
    DONE[label] = entry
    save()
    mark = "OK " if as_expected else ("?? " if as_expected is None else "NO ")
    print(f"{mark}{label}: {s.get('result')} {json.dumps(ret, default=str)[:300]}", flush=True)
    return entry


def tx_time(entry):
    return unix(entry["created_at"])


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


def page_has(url, text, tries=40):
    for _ in range(tries):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url + f"?nocache={int(time.time())}", headers={"User-Agent": "lcc2-live"}), timeout=20).read().decode()
            if text in body:
                return True
        except Exception:
            pass
        time.sleep(15)
    return False


def correct_pages(coin):
    """Make and push the corrected pages for one coin; wait until the public pages show the correction."""
    if any(p["coin"] == coin for p in rec["page_changes"]):
        return
    gen = [sys.executable, str(ROOT / "tools" / "make_v2_pages.py"), str(CHECKER_REPO / "web" / "public"), str(DEMO_REPO), "--corrected", coin]
    subprocess.run(gen, check=True, capture_output=True)
    commits = {}
    for repo, paths, extra in ((CHECKER_REPO, ["web/public/v2", "docs/v2"], True), (DEMO_REPO, ["."], False)):
        if extra:
            subprocess.run(["cp", "-r", str(repo / "web/public/v2/."), str(repo / "docs/v2/")], check=True)
        subprocess.run(["git", "-C", str(repo), "add", *paths], check=True)
        msg = f"Fictional explorer data correction for {coin} (live run of Launch Claim Checker v2)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01PmboiXeSxAX9LMvc5cn1bn\n"
        r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=Brilliant Nodes", "-c", "user.email=noreply@brilliantnodes.com", "commit", "-q", "-m", msg], capture_output=True, text=True)
        if r.returncode == 0:
            branch = "HEAD:main"
            subprocess.run(["git", "-C", str(repo), "-c", "push.negotiate=true", "push", "-q", "origin", branch], check=True, capture_output=True)
            if repo == CHECKER_REPO:
                subprocess.run(["git", "-C", str(repo), "-c", "push.negotiate=true", "push", "-q", "origin", "HEAD:milestone-two-explorers"], capture_output=True)
        commits[repo.name] = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    live = {"a": page_has(A.format(c=coin), "Correction (fictional)") if coin == "flipcoin" else None,
            "b": page_has(B.format(c=coin), "Data correction (fictional)")}
    rec["page_changes"].append({"coin": coin, "commits": commits, "live": live, "at": int(time.time())})
    save()
    print(f"pages corrected for {coin}: {commits} live={live}", flush=True)


def times(entry_bond):
    tb = tx_time(entry_bond)
    close = tb + WIN
    return {"tb": tb, "close": close, "rc_open": close + WIN, "rc_end": close + 2 * WIN, "nc_from": close + 3 * WIN}


# ------------------------------------------------------------------ setup

for r in ADDR:
    if balance(C[r], ADDR[r]) < 10 * G:
        fund(C[r], ADDR[r], 20)
if "address" not in rec:
    rec["deploy"] = deploy(C["requester"], SOURCE.read_text(), [WIN, WIN, WIN, WIN])
    rec["address"] = rec["deploy"]["address"]
    save()
    print("deployed", rec["deploy"], flush=True)

# ------------------------------------------------------------------ the free checks

CHECKS = [
    ("check 1 Examplecoin NO_FOUNDER_REWARD", [A.format(c="examplecoin"), B.format(c="examplecoin"), "Examplecoin", "NO_FOUNDER_REWARD", "No founder reward"], {"verdict": "CONTRADICTED", "rule": "BOTH:P1"}),
    ("check 2 Controlcoin NO_PREMINE", [A.format(c="controlcoin"), B.format(c="controlcoin"), "Controlcoin", "NO_PREMINE", "No premine"], {"verdict": "SUPPORTED", "rule": "BOTH:P2"}),
    ("check 3 Examplecoin DECENTRALIZED_MINING", [A_MINE, B_MINE, "Examplecoin", "DECENTRALIZED_MINING", "Decentralised mining"], {"verdict": "CONTRADICTED", "rule": "BOTH:M1"}),
    ("check 4 Splitcoin NO_FOUNDER_REWARD (explorers disagree)", [A.format(c="splitcoin"), B.format(c="splitcoin"), "Splitcoin", "NO_FOUNDER_REWARD", ""], {"verdict": "UNDETERMINED", "rule": "D1_EXPLORERS_DISAGREE"}),
    ("check 5 Examplecoin, explorer B shows another coin", [A.format(c="examplecoin"), B.format(c="controlcoin"), "Examplecoin", "NO_FOUNDER_REWARD", ""], {"verdict": "UNDETERMINED", "rule": "W1_WRONG_PAGE"}),
    ("check 6 Examplecoin mining, planted instruction on B", [A_MINE, B_PLANTED, "Examplecoin", "DECENTRALIZED_MINING", ""], {"verdict": "CONTRADICTED", "rule": "BOTH:M1"}),
]
for label, args, expect in CHECKS:
    step(label, "requester", "check_claim", args, 0, expect)
if ONLY_CHECKS:
    raise SystemExit(0)

MONEY_CHECKS = [
    ("check 7 Flipcoin NO_FOUNDER_REWARD", [A.format(c="flipcoin"), B.format(c="flipcoin"), "Flipcoin", "NO_FOUNDER_REWARD", ""], {"verdict": "CONTRADICTED", "rule": "BOTH:P1"}),
    ("check 8 Driftcoin NO_FOUNDER_REWARD", [A.format(c="driftcoin"), B.format(c="driftcoin"), "Driftcoin", "NO_FOUNDER_REWARD", ""], {"verdict": "CONTRADICTED", "rule": "BOTH:P1"}),
    ("check 9 Examplecoin NO_PREMINE", [A.format(c="examplecoin"), B.format(c="examplecoin"), "Examplecoin", "NO_PREMINE", ""], {"verdict": "CONTRADICTED", "rule": "BOTH:P1"}),
]
for label, args, expect in MONEY_CHECKS:
    step(label, "requester", "check_claim", args, 0, expect)


def cid(label):
    return str((DONE[label].get("returned") or {}).get("id"))


ids = {n: cid(l) for n, (l, _a, _e) in zip((1, 2, 3, 4, 5, 6), CHECKS)}
ids.update({n: cid(l) for n, (l, _a, _e) in zip((7, 8, 9), MONEY_CHECKS)})

# ------------------------------------------------------------------ bonds

bonds = {}
for n in (1, 2, 7, 8, 9):
    bonds[n] = step(f"bond check {n}", "requester", "bond", [ids[n]], BOND, {"ok": True, "bonded": str(BOND)})
step("bond check 3 (mining verdict)", "requester", "bond", [ids[3]], BOND, "refused:BOTH:P1 or BOTH:P2")
step("bond check 4 (explorers disagree)", "requester", "bond", [ids[4]], BOND, "refused:BOTH:P1 or BOTH:P2")
step("challenge check 2 by challenger1 with the wrong amount", "challenger1", "challenge", [ids[2]], BOND - 1, "refused:exactly the bond")

# ------------------------------------------------------------------ challenges

step("challenge check 1 by challenger1", "challenger1", "challenge", [ids[1]], BOND, {"ok": True, "challenger": 1})
step("challenge check 1 by challenger2", "challenger2", "challenge", [ids[1]], BOND, {"ok": True, "challenger": 2})
step("challenge check 1 by the requester", "requester", "challenge", [ids[1]], BOND, "refused:the requester cannot")
step("challenge check 1 again by challenger1", "challenger1", "challenge", [ids[1]], BOND, "refused:already challenged")
step("challenge check 7 by challenger1", "challenger1", "challenge", [ids[7]], BOND, {"ok": True, "challenger": 1})
step("challenge check 8 by challenger2", "challenger2", "challenge", [ids[8]], BOND, {"ok": True, "challenger": 1})
step("challenge check 9 by challenger1", "challenger1", "challenge", [ids[9]], BOND, {"ok": True, "challenger": 1})

correct_pages("flipcoin")
correct_pages("driftcoin")

T = {n: times(bonds[n]) for n in bonds}
wait_until(T[2]["close"] + 5, "check 2's challenge window to close")
step("challenge check 2 after the window", "challenger1", "challenge", [ids[2]], BOND, "refused:window has closed")

# ------------------------------------------------------------------ re-checks and settles

wait_until(max(T[n]["rc_open"] for n in (1, 2, 7, 8)) + 5, "the re-check windows to open")
step("settle check 2 (no challenger)", "requester", "settle", [ids[2]], 0, {"ok": True, "state": "RELEASED"})
step("recheck check 1", "challenger1", "recheck", [ids[1]], 0, {"ok": True, "decided": True, "state": "UPHELD"})
step("recheck check 7 (both explorers corrected block 1)", "challenger1", "recheck", [ids[7]], 0, {"ok": True, "decided": True, "state": "OVERTURNED"})
step("recheck check 8 (only Blockfield corrected block 1)", "challenger2", "recheck", [ids[8]], 0, {"ok": True, "decided": True, "state": "NOT_CONFIRMED"})
wait_until(T[9]["nc_from"] + 5, "check 9's re-check time to pass with no re-check")
step("settle check 9 (no re-check was run)", "challenger1", "settle", [ids[9]], 0, {"ok": True, "state": "NOT_CONFIRMED"})

# ------------------------------------------------------------------ collect and withdraw

owed = {
    (1, "requester"): 3 * BOND, (1, "challenger1"): 0, (1, "challenger2"): 0,
    (2, "requester"): BOND,
    (7, "requester"): 0, (7, "challenger1"): 2 * BOND,
    (8, "requester"): BOND, (8, "challenger2"): BOND,
    (9, "requester"): BOND, (9, "challenger1"): BOND,
}
for (n, who), amount in owed.items():
    step(f"collect check {n} by {who}", who, "collect", [ids[n]], 0, {"ok": True, "credited": str(amount)})

for who in ADDR:
    claim = int(read(C[who], rec["address"], "get_claimable", [ADDR[who]]))
    if claim > 0:
        step(f"withdraw {who}", who, "withdraw", [0], 0, {"ok": True, "amount": str(claim)})

# ------------------------------------------------------------------ checks against the views

v = {n: read(C["requester"], rec["address"], "get_check", [ids[n]]) for n in ids}
for n, (label, _a, expect) in list(zip((1, 2, 3, 4, 5, 6), CHECKS)) + list(zip((7, 8, 9), MONEY_CHECKS)):
    r = v[n]["result"]
    check_view(f"check {n} stored as {expect['rule']}", r["verdict"] == expect["verdict"] and r["rule"] == expect["rule"], r)
for n, st in ((1, "UPHELD"), (2, "RELEASED"), (7, "OVERTURNED"), (8, "NOT_CONFIRMED"), (9, "NOT_CONFIRMED"), (3, "NONE"), (4, "NONE")):
    check_view(f"check {n} bond state {st}", v[n]["bond"]["state"] == st, v[n]["bond"])
check_view("check 7 shows the overturning verdict", (v[7]["bond"].get("recheck") or {}).get("verdict") == "SUPPORTED", v[7]["bond"].get("recheck"))
t = read(C["requester"], rec["address"], "totals", [])
check_view("totals: nothing locked or credited at the end", t["locked"] == "0" and t["credited"] == "0", t)
check_view("contract balance is zero", balance(C["requester"], rec["address"]) == 0, balance(C["requester"], rec["address"]))
check_view("challengers of check 1", [x.lower() for x in read(C["requester"], rec["address"], "get_challengers", [ids[1]])] == [ADDR["challenger1"].lower(), ADDR["challenger2"].lower()], None)
rec["summary"] = {"steps": len(rec["steps"]), "steps_as_expected": sum(1 for s in rec["steps"] if s["as_expected"]),
                  "checks": len(rec["checks"]), "checks_ok": sum(1 for c in rec["checks"] if c["ok"])}
save()
print(json.dumps(rec["summary"]), flush=True)
