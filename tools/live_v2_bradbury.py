#!/usr/bin/env python3
"""Live cases for LaunchClaimCheckerV2 on GenLayer Testnet Bradbury Phase 2 (packed GenVM v0.6 build).

    cd tools/bradbury && npm ci && cd ../..
    LCC2_KEYS=/path/to/keys DEMO_REPO=/path/to/demo-explorer python tools/live_v2_bradbury.py [record.json] [--resume]

Three testnet wallets whose keys stay in files outside the repository, never
printed: LCC2_KEYS/lcc_v2_bradbury.key (the requester, which deployed the
contract) and lcc2_bradbury_challenger{1,2}.key (made here if missing and
funded from the requester). The contract was deployed with the 600-second
floor for all four windows.

Bradbury transactions carry no return value. Every step is recorded with the
chain's own outcome (consensus result, execution result, each validator's
vote) and the views are read afterwards. bond() and challenge() never raise:
a refused one finishes normally and credits the GEN back, so a refusal is
shown by the caller's credit rising by exactly the amount sent. recheck(),
settle() and collect() raise when refused.

The same stories as tools/live_v2_money.py on Studio. Turncoin and Veercoin
stand in for Flipcoin and Driftcoin, so that the Studio run's corrected pages
stay as they were. All coins and both explorers are fictional.
"""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from genlayer_py import create_account

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "tools" / "bradbury"
KEYS = Path(os.environ.get("LCC2_KEYS", str(Path.home() / ".lcc2-keys")))
DEMO_REPO = Path(os.environ.get("DEMO_REPO", str(ROOT.parent / "demo-explorer")))
RESUME = "--resume" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(_args[0]) if _args else ROOT / "examples" / "live" / "v2-bradbury.json"
BUILD = ROOT / "bradbury" / "build" / "launch_claim_checker_v2.py"
ADDRESS = os.environ.get("LCC2_BRADBURY", "0xC1b4AD9cd4D1609461B6eabbBb78a0B1F4FC8E22")
DEPLOY_TX = "0xbddd1d3a9f7ebeb7abab9173c8346f64a22700cba511d7f13e3ffe94c80dd96f"
G = 10**18
BOND = G // 10
A_URL = "https://checker.brilliantnodes.com/v2/{c}-block-1.html"
B_URL = "https://brilliantnodes.github.io/demo-explorer/{c}/block-1.html"
A_MINE = "https://checker.brilliantnodes.com/v2/examplecoin-mining.html"
B_MINE = "https://brilliantnodes.github.io/demo-explorer/examplecoin/pools.html"
NOTHING_STORED = ("UNDETERMINED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT", "CANCELED")
VOTE = {0: "NOT_VOTED", 1: "FINISHED_WITH_RETURN", 2: "FINISHED_WITH_ERROR", 3: "TIMEOUT", 4: "NONDET_DISAGREE", 5: "DETERMINISTIC_VIOLATION"}

ROLES = ("requester", "challenger1", "challenger2")
KEY = {"requester": KEYS / "lcc_v2_bradbury.key", "challenger1": KEYS / "lcc2_bradbury_challenger1.key", "challenger2": KEYS / "lcc2_bradbury_challenger2.key"}
for r in ROLES[1:]:
    if not KEY[r].exists():
        KEY[r].write_text("0x" + secrets.token_hex(32) + "\n")
        KEY[r].chmod(0o600)
ADDR = {r: create_account(KEY[r].read_text().strip()).address for r in ROLES}

rec = {"network": "testnet-bradbury-phase-2", "chain_id": 4221, "build": "bradbury/build/launch_claim_checker_v2.py (GenVM v0.6)",
       "build_sha256": hashlib.sha256(BUILD.read_bytes()).hexdigest(), "address": ADDRESS, "deploy_tx": DEPLOY_TX,
       "windows_seconds": [600] * 4, "bond_wei": str(BOND), "accounts": ADDR, "steps": [], "checks": [], "page_changes": [], "cases": {}}
if RESUME:
    rec = json.loads(OUT.read_text())
    assert rec["accounts"] == ADDR, "the record was made with other keys"
DONE = {s["label"]: s for s in rec["steps"]}


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


def node(role, *args, timeout=1800):
    """A write is never sent twice: once it has a hash, a failure only means waiting longer for that transaction."""
    env = {**os.environ, "BRADBURY_KEY_FILE": str(KEY[role]), "NODE_USE_ENV_PROXY": "1", "NODE_NO_WARNINGS": "1"}
    d = {"ok": False, "error": "no result"}
    for _attempt in range(3):
        try:
            p = subprocess.run(["node", "gl.mjs", *args], cwd=JS, capture_output=True, text=True, timeout=timeout, env=env)
            out = p.stdout
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        objs = []
        for ln in out.splitlines():
            if ln.startswith("{"):
                try:
                    objs.append(json.loads(ln))
                except ValueError:
                    pass
        sent = next((o["sent"] for o in objs if "sent" in o), None)
        d = next((o for o in reversed(objs) if "ok" in o), {"ok": False, "error": "no result"})
        if d.get("ok"):
            return d
        if args[0] in ("write", "deploy") and (sent or d.get("hash")):
            return wait(sent or d.get("hash"))
        time.sleep(15)
    return d


def tx(h):
    return node("requester", "tx", h, timeout=300).get("raw") or {}


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


def read(fn, args=None):
    for _ in range(4):
        d = node("requester", "read", ADDRESS, fn, json.dumps(args or [], default=str), timeout=300)
        if d.get("ok"):
            return d["result"]
        time.sleep(10)
    raise RuntimeError(f"read {fn}: {d.get('error')}")


def balance(addr) -> int:
    return int(node("requester", "balance", addr, timeout=120)["result"])


def claimable(role) -> int:
    return int(read("get_claimable", [ADDR[role]]))


def check(label, value, want=None):
    """A view read right after a transaction can still show the state before it; a callable is read again, up to a minute."""
    reads = 0
    while True:
        got = value() if callable(value) else value
        reads += 1
        ok = bool(got) if want is None else got == want
        if ok or not callable(value) or reads >= 7:
            break
        time.sleep(10)
    rec["checks"].append({"label": label, "value": got, "want": want, "ok": ok, "reads": reads, "at": int(time.time())})
    save()
    print(f"   check {'ok ' if ok else 'FAILED '}{label}: {json.dumps(got, default=str)[:220]}", flush=True)
    return ok


def step(label, role, fn, args, value=0, raises=False, credited_back=False, payees=""):
    """One transaction. raises: the contract is expected to refuse it with an error.
    credited_back: a refused bond or challenge, which finishes normally and credits the GEN back."""
    if label in DONE:
        return DONE[label]
    due()
    for _ in range(40):  # the fee budget is paid up front; wait for earlier refunds if the wallet is low
        if balance(ADDR[role]) >= value + 15 * G // 100:
            break
        time.sleep(15)
    before = claimable(role) if credited_back else None
    t0 = time.time()
    d = node(role, "write", ADDRESS, fn, json.dumps(args, default=str), str(value), payees)
    h = d.get("hash")
    if h and not decided(d.get("raw") or {}):
        d = wait(h)
    if h and str((d.get("raw") or {}).get("statusName")) in ("LEADER_TIMEOUT", "VALIDATORS_TIMEOUT"):
        d = wait(h, final=True)
    raw = d.get("raw") or {}
    st = str(raw.get("statusName", ""))
    result = st if st in NOTHING_STORED else (raw.get("resultName") or d.get("error"))
    execution = raw.get("txExecutionResultName")
    votes = [VOTE.get(v, str(v)) for v in (raw.get("lastRound") or {}).get("validatorVotes") or []]
    ok = result == "MAJORITY_AGREE" and ((execution != "FINISHED_WITH_RETURN") if raises else (execution == "FINISHED_WITH_RETURN"))
    row = {"n": len(rec["steps"]) + 1, "label": label, "who": role, "from": ADDR[role], "method": fn, "args": args, "value": str(value), "tx": h,
           "expected": "refused with an error" if raises else ("refused, GEN credited back" if credited_back else "accepted"),
           "result": result, "execution": execution, "validators": {"of": len(votes), "same_as_the_result": sum(1 for v in votes if v == execution), "votes": votes},
           "created": raw.get("createdTimestamp"), "seconds": int(time.time() - t0), "as_expected": ok}
    if credited_back and ok:
        reads = 0
        while True:
            after = claimable(role)
            reads += 1
            if after - before == value or reads >= 7:
                break
            time.sleep(10)
        row["credited_back"] = str(after - before)
        row["as_expected"] = ok = after - before == value
    rec["steps"].append(row)
    DONE[label] = row
    save()
    print(f"{row['n']:2d} {'ok ' if ok else 'NOT AS EXPECTED '}{label}: {result} {execution} {row['validators']['same_as_the_result']} of "
          f"{row['validators']['of']} validators {h} ({row['seconds']} s){' credited back ' + row['credited_back'] if 'credited_back' in row else ''}", flush=True)
    return row


def new_check(case, args, verdict, rule):
    """A check, then its id from the views. If the validators did not agree (nothing recorded), once more."""
    if case in rec["cases"]:
        return rec["cases"][case]["id"]
    for attempt in ("", " (retry)"):
        before = int(read("get_count"))
        row = step(f"case {case} check{attempt}", "requester", "check_claim", args)
        if row["result"] != "MAJORITY_AGREE":
            continue
        n = before
        for _ in range(7):
            n = int(read("get_count"))
            if n > before:
                break
            time.sleep(10)
        if n <= before:
            continue
        cid = str(n)
        v = read("get_check", [cid])
        rec["cases"][case] = {"id": cid, "check_tx": row["tx"]}
        save()
        check(f"case {case}: check {cid} is {verdict} {rule}", [v["result"]["verdict"], v["result"]["rule"], v["requester"].lower(), v.get("coin_name") or args[2]],
              [verdict, rule, ADDR["requester"].lower(), args[2]])
        return cid
    raise SystemExit(f"case {case}: no agreed check after two attempts")


def page_has(url, text, tries=40):
    for _ in range(tries):
        try:
            req = urllib.request.Request(url + f"?nocache={int(time.time())}", headers={"User-Agent": "lcc2-live"})
            if text in urllib.request.urlopen(req, timeout=20).read().decode():
                return True
        except Exception:
            pass
        due()
        time.sleep(15)
    return False


def correct_pages(coin):
    """Write and push the corrected pages for one coin (tools/make_v2_pages.py --corrected), keeping the Studio run's corrections."""
    if any(p["coin"] == coin for p in rec["page_changes"]):
        return
    done = ["flipcoin", "driftcoin"] + [p["coin"] for p in rec["page_changes"]] + [coin]
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_v2_pages.py"), str(ROOT / "web" / "public"), str(DEMO_REPO), "--corrected", ",".join(done)], check=True, capture_output=True)
    shutil.copytree(ROOT / "web" / "public" / "v2", ROOT / "docs" / "v2", dirs_exist_ok=True)
    msg = (f"Fictional explorer data correction for {coin} (Bradbury live run of Launch Claim Checker v2)\n\n"
           "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01PmboiXeSxAX9LMvc5cn1bn\n")
    commits = {}
    for repo, paths, branches in ((ROOT, ["web/public/v2", "docs/v2"], ["main", "milestone-two-explorers"]), (DEMO_REPO, ["."], ["main"])):
        subprocess.run(["git", "-C", str(repo), "add", *paths], check=True)
        r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=Brilliant Nodes", "-c", "user.email=noreply@brilliantnodes.com", "commit", "-q", "-m", msg], capture_output=True, text=True)
        if r.returncode == 0:
            for b in branches:
                subprocess.run(["git", "-C", str(repo), "-c", "push.negotiate=true", "push", "-q", "origin", f"HEAD:{b}"], check=True, capture_output=True)
        commits[repo.name] = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    live = {"a": page_has(A_URL.format(c=coin), "Correction (fictional)") if coin == "turncoin" else None,
            "b": page_has(B_URL.format(c=coin), "Data correction (fictional)")}
    rec["page_changes"].append({"coin": coin, "commits": commits, "live": live, "at": int(time.time())})
    save()
    print(f"pages corrected for {coin}: {commits} live={live}", flush=True)


def times(case):
    t = read("get_check", [rec["cases"][case]["id"]]).get("times") or {}
    rec["cases"][case]["times"] = t
    return {k: int(v) for k, v in t.items()}


OUTCOMES = []  # (case, time key, offset, label, role, fn, kwargs), each run as soon as it is due
_busy = [False]


def due():
    if _busy[0]:
        return
    _busy[0] = True
    try:
        for case, key, off, label, role, fn, kw in OUTCOMES:
            if label in DONE or f"bond case {case}" not in DONE:
                continue
            t = rec["cases"][case].get("times") or times(case)
            if time.time() >= int(t[key]) + off:
                step(label, role, fn, [rec["cases"][case]["id"]], **kw)
    finally:
        _busy[0] = False


def bond(case):
    step(f"bond case {case}", "requester", "bond", [rec["cases"][case]["id"]], BOND)
    check(f"case {case}: bonded", lambda: read("get_check", [rec["cases"][case]["id"]])["bond"]["state"], "BONDED")
    times(case)
    save()


def challengers(case):
    return [x.lower() for x in read("get_challengers", [rec["cases"][case]["id"]])]


# ------------------------------------------------------------------ setup

for r in ROLES[1:]:
    if balance(ADDR[r]) < 2 * G:
        before = balance(ADDR[r])
        d = node("requester", "send", ADDR[r], str(3 * G))
        for _ in range(60):
            if balance(ADDR[r]) >= before + 3 * G:
                break
            time.sleep(10)
        rec.setdefault("funding", []).append({"to": ADDR[r], "wei": str(3 * G), "tx": d.get("hash"), "arrived": balance(ADDR[r]) >= before + 3 * G})
        save()
        print("funded", r, rec["funding"][-1], flush=True)
check("contract rules: four windows of 600 s", lambda: read("get_rules")["windows_seconds"], {"bond_win": 600, "ch_win": 600, "grace": 600, "rc_win": 600})

OUTCOMES += [
    ("B", "close", 5, "challenge B after the window", "challenger2", "challenge", {"value": BOND, "credited_back": True}),
    ("A", "rc_open", 5, "recheck A", "challenger1", "recheck", {}),
    ("B", "rc_open", 5, "settle B (no challenger)", "challenger1", "settle", {}),
    ("C", "rc_open", 5, "recheck C (both explorers corrected block 1)", "challenger1", "recheck", {}),
    ("D", "rc_open", 5, "recheck D (only Blockfield corrected block 1)", "challenger2", "recheck", {}),
    ("E", "nc_from", 5, "settle E (no re-check was run)", "challenger1", "settle", {}),
]
P1 = ("CONTRADICTED", "BOTH:P1")

new_check("A", [A_URL.format(c="examplecoin"), B_URL.format(c="examplecoin"), "Examplecoin", "NO_FOUNDER_REWARD", "No founder reward"], *P1)
bond("A")
step("challenge A by challenger1", "challenger1", "challenge", [rec["cases"]["A"]["id"]], BOND)
step("challenge A by challenger2", "challenger2", "challenge", [rec["cases"]["A"]["id"]], BOND)
step("challenge A by the requester", "requester", "challenge", [rec["cases"]["A"]["id"]], BOND, credited_back=True)
step("challenge A again by challenger1", "challenger1", "challenge", [rec["cases"]["A"]["id"]], BOND, credited_back=True)
check("case A: two challengers, in order", lambda: challengers("A"), [ADDR["challenger1"].lower(), ADDR["challenger2"].lower()])

new_check("B", [A_URL.format(c="controlcoin"), B_URL.format(c="controlcoin"), "Controlcoin", "NO_PREMINE", "No premine"], "SUPPORTED", "BOTH:P2")
bond("B")
step("challenge B with the wrong amount", "challenger1", "challenge", [rec["cases"]["B"]["id"]], BOND - 1, credited_back=True)
step("settle B too early", "challenger1", "settle", [rec["cases"]["B"]["id"]], raises=True)

new_check("C", [A_URL.format(c="turncoin"), B_URL.format(c="turncoin"), "Turncoin", "NO_FOUNDER_REWARD", ""], *P1)
bond("C")
step("challenge C by challenger1", "challenger1", "challenge", [rec["cases"]["C"]["id"]], BOND)
correct_pages("turncoin")

new_check("D", [A_URL.format(c="veercoin"), B_URL.format(c="veercoin"), "Veercoin", "NO_FOUNDER_REWARD", ""], *P1)
bond("D")
step("challenge D by challenger2", "challenger2", "challenge", [rec["cases"]["D"]["id"]], BOND)
correct_pages("veercoin")

new_check("E", [A_URL.format(c="examplecoin"), B_URL.format(c="examplecoin"), "Examplecoin", "NO_PREMINE", ""], *P1)
bond("E")
step("challenge E by challenger1", "challenger1", "challenge", [rec["cases"]["E"]["id"]], BOND)
step("recheck E too early", "challenger1", "recheck", [rec["cases"]["E"]["id"]], raises=True)

new_check("F-mining", [A_MINE, B_MINE, "Examplecoin", "DECENTRALIZED_MINING", ""], "CONTRADICTED", "BOTH:M1")
step("bond on a mining verdict", "requester", "bond", [rec["cases"]["F-mining"]["id"]], BOND, credited_back=True)
new_check("F-disagree", [A_URL.format(c="splitcoin"), B_URL.format(c="splitcoin"), "Splitcoin", "NO_FOUNDER_REWARD", ""], "UNDETERMINED", "D1_EXPLORERS_DISAGREE")
step("bond on explorers that disagree", "requester", "bond", [rec["cases"]["F-disagree"]["id"]], BOND, credited_back=True)

# ------------------------------------------------------------------ outcomes, each as soon as it is due

while any(o[3] not in DONE for o in OUTCOMES):
    due()
    left = [int(rec["cases"][o[0]]["times"][o[1]]) + o[2] - time.time() for o in OUTCOMES if o[3] not in DONE]
    if left:
        print(f"... next outcome step in {int(max(0, min(left)))} s", flush=True)
        time.sleep(max(5, min(30, min(left))))

for c, st in (("A", "UPHELD"), ("B", "RELEASED"), ("C", "OVERTURNED"), ("D", "NOT_CONFIRMED"), ("E", "NOT_CONFIRMED")):
    check(f"case {c}: bond state {st}", lambda c=c: read("get_check", [rec["cases"][c]["id"]])["bond"]["state"], st)
check("case C: the re-check found SUPPORTED BOTH:P2", lambda: [(read("get_check", [rec["cases"]["C"]["id"]])["bond"].get("recheck") or {}).get(k) for k in ("verdict", "rule")], ["SUPPORTED", "BOTH:P2"])
check("case D: the re-check found the explorers disagree", lambda: (read("get_check", [rec["cases"]["D"]["id"]])["bond"].get("recheck") or {}).get("rule"), "D1_EXPLORERS_DISAGREE")

# ------------------------------------------------------------------ collect and withdraw

owed = [("A", "requester", 3 * BOND), ("A", "challenger1", 0), ("B", "requester", BOND), ("C", "challenger1", 2 * BOND), ("D", "requester", BOND),
        ("D", "challenger2", BOND), ("E", "requester", BOND), ("E", "challenger1", BOND)]
for case, role, amount in owed:
    before = claimable(role)
    step(f"collect {case} by {role}", role, "collect", [rec["cases"][case]["id"]])
    check(f"collect {case} by {role}: credited {amount}", lambda role=role, before=before: claimable(role) - before, amount)
step("collect A by the requester again", "requester", "collect", [rec["cases"]["A"]["id"]], raises=True)
for role in ROLES:
    have = claimable(role)
    if have > 0:
        row = step(f"withdraw {role}", role, "withdraw", [0], payees=ADDR[role])
        msgs = [{"to": str(m.get("recipient")).lower(), "wei": str(int(str(m.get("value")), 0))} for m in (tx(row["tx"]).get("messages") or [])]
        check(f"withdraw {role}: one transfer of {have} to itself", msgs, [{"to": ADDR[role].lower(), "wei": str(have)}])
        check(f"withdraw {role}: nothing left credited", lambda role=role: claimable(role), 0)
t = read("totals")
check("totals: nothing locked or credited at the end", [t["locked"], t["credited"]], ["0", "0"])
check("contract balance is zero", lambda: balance(ADDRESS), 0)
rec["summary"] = {"steps": len(rec["steps"]), "steps_as_expected": sum(1 for s in rec["steps"] if s["as_expected"]),
                  "checks": len(rec["checks"]), "checks_ok": sum(1 for c in rec["checks"] if c["ok"])}
save()
print(json.dumps(rec["summary"]), flush=True)
