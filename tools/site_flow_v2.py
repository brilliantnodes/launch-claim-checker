#!/usr/bin/env python3
"""Use the v2 page (two explorers, a bond and a challenge) as a visitor would, in a headless browser, against the Studio contract it names.

    pip install playwright genlayer-py==0.19.0 && playwright install chromium
    python tools/site_flow_v2.py [page address] [record.json]

Defaults: https://checker.brilliantnodes.com/two-explorers.html and
examples/live/v2-site-studio.json.

Every step is a click on the page: three temporary accounts, the Examplecoin
example checked on both explorers, a bond of 1 test GEN, two challenges, the
re-check once its window opens (about 20 minutes later), collect and
withdraw. The page makes the keys in the browser; this script holds none.
After each click the transaction hash is read from the page; at the end every
transaction is read back from Studio with what the chain has. All coins are
fictional.
"""
import base64
import json
import sys
import time
from pathlib import Path

from genlayer_py.abi import calldata
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import client, read, summary, tx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://checker.brilliantnodes.com/two-explorers.html"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "examples" / "live" / "v2-site-studio.json"
ENDINGS = ("Accepted", "refused", "did not", "Not settled", "The validators")
ROLES = ("requester", "challenger1", "challenger2")
rec = {"page": URL, "network": "GenLayer Studio (studionet)", "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": [], "page_errors": []}


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


with sync_playwright() as p:
    chrome = Path("/usr/bin/google-chrome")
    browser = p.chromium.launch(executable_path=str(chrome), args=["--no-sandbox"]) if chrome.exists() else p.chromium.launch()
    pg = browser.new_page(viewport={"width": 1000, "height": 1400})
    pg.on("pageerror", lambda e: rec["page_errors"].append(str(e)[:300]))
    pg.goto(URL, wait_until="networkidle")
    time.sleep(4)
    rec["contract"] = pg.inner_text("#foot-contract").split()[-1]
    rec["windows_line"] = pg.inner_text("#windows-line")

    def done(what, seconds=480):
        """Wait for the page to report how the transaction ended; return the note it shows."""
        end = time.time() + seconds
        note, h = "", None
        before = {s["tx"] for s in rec["steps"]}
        time.sleep(2)
        while time.time() < end:
            note = pg.inner_text("#life-note")
            code = pg.locator("#life-hash code")
            h = code.first.inner_text().strip() if code.count() else None
            if h and h not in before and any(note.startswith(e) for e in ENDINGS):
                break
            time.sleep(3)
        rec["steps"].append({"n": len(rec["steps"]) + 1, "click": what, "page_says": note, "tx": h})
        save()
        print(f"{len(rec['steps']):2d} {what}: {note[:120]} {h}", flush=True)
        time.sleep(4)
        return note

    for role in ROLES:
        pg.click(f'[data-temp="{role}"]')
        pg.click(f'[data-fund="{role}"]')
        time.sleep(6)
    rec["accounts"] = {role: pg.inner_text(f"#{role}-addr").split()[-1] for role in ROLES}
    newest = lambda: pg.locator("#list article").first  # noqa: E731

    pg.click('[data-example="exm"]')
    pg.click("#btn-check")
    done("Example 'Examplecoin, no founder reward', then 'Check as Requester'")
    rec["check_as_the_page_shows_it"] = newest().inner_text()[:1500]
    newest().get_by_role("button", name="Bond as Requester").click()
    done("'Bond as Requester' with the default 1 test GEN")
    newest().get_by_role("button", name="Challenge as Challenger", exact=True).click()
    done("'Challenge as Challenger'")
    newest().get_by_role("button", name="Challenge as Second challenger").click()
    done("'Challenge as Second challenger'")
    rec["bond_as_the_page_shows_it"] = newest().inner_text()[:1500]

    # The re-check window opens after the challenge window and the grace period.
    for _ in range(90):
        pg.click("#refresh")
        time.sleep(20)
        if newest().get_by_role("button", name="Re-check now").count():
            break
    newest().get_by_role("button", name="Re-check now").click()
    done("'Re-check now', once the page shows it")
    rec["outcome_as_the_page_shows_it"] = newest().inner_text()[:1800]
    newest().get_by_role("button", name="Collect as Requester").click()
    done("'Collect as Requester'")
    newest().get_by_role("button", name="Collect as Challenger", exact=True).click()
    done("'Collect as Challenger' (an upheld check gives a challenger nothing)")
    pg.locator("#requester-bal button").click()
    done("'Withdraw' next to the Requester's balance")
    browser.close()

c, _acct = client()
for s in rec["steps"]:
    if not s["tx"]:
        continue
    t = tx(c, s["tx"])
    try:
        call = calldata.decode(base64.b64decode((t.get("data") or {}).get("calldata") or ""))
    except Exception:
        call = {}
    s["on_chain"] = {"from": t.get("from_address"), "to": t.get("to_address"), "value": str(t.get("value") or 0), "method": call.get("method", call.get("")), "args": call.get("args"), **summary(t)}
G = 10**18
want = [("check_claim", "requester", {"rule": "BOTH:P1", "verdict": "CONTRADICTED"}), ("bond", "requester", {"bonded": str(G)}),
        ("challenge", "challenger1", {"challenger": 1}), ("challenge", "challenger2", {"challenger": 2}),
        ("recheck", "challenger1", {"state": "UPHELD"}), ("collect", "requester", {"credited": str(3 * G)}),
        ("collect", "challenger1", {"credited": "0"}), ("withdraw", "requester", {"amount": str(3 * G)})]
ok = len(rec["steps"]) == len(want)
for s, (method, role, expect) in zip(rec["steps"], want):
    oc = s.get("on_chain") or {}
    r = oc.get("returned") if isinstance(oc.get("returned"), dict) else {}
    good = oc.get("method") == method and oc.get("execution") == "SUCCESS" and r.get("ok", True) is not False and all(r.get(k) == v for k, v in expect.items())
    good = good and str(oc.get("from", "")).lower() == rec["accounts"][role].lower()
    s["as_expected"] = good
    ok = ok and good
rec["totals_after"] = read(c, rec["contract"], "totals")
rec["summary"] = {"clicks_that_sent_a_transaction": len(rec["steps"]), "as_expected": sum(1 for s in rec["steps"] if s.get("as_expected")), "page_errors": len(rec["page_errors"])}
save()
print(json.dumps(rec["summary"]))
sys.exit(0 if ok and not rec["page_errors"] else 1)
